"""Clasificador de la dirección del precio de la semana siguiente (Fase 3, contrato 5.4).

Entrada: `gold.features_modelo` en pandas. Objetivo: `direccion_siguiente` (sube, baja,
se_mantiene) por combustible, con un modelo global y one-hot del combustible.

- Validación **temporal**: las últimas `n_test` semanas con objetivo conocido son la prueba; todo
  lo anterior es entrenamiento. Nunca se mezcla el futuro con el pasado.
- Línea base: la dirección de la semana siguiente es igual a la de la semana actual.
- Modelos: regresión logística y árbol de decisión (sklearn). Los nulos de las variables (semanas
  después de un hueco del MEM, WTI o subsidio sin dato) se imputan con la mediana del
  entrenamiento y se agrega un indicador de nulo; las filas sin `direccion_actual` se descartan.
- Se elige el modelo con mejor F1 macro en prueba solo si supera a la línea base; si no, el
  "modelo" elegido es la línea base (resultado válido que se documenta).

Este módulo no depende de Spark ni de MLflow: `pipelines/03_gold.py` registra en MLflow y
escribe las tablas; aquí se puede probar todo con datos sintéticos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

CLASES = ["baja", "se_mantiene", "sube"]
COMBUSTIBLES = ["super", "regular", "diesel"]
NUMERICAS = ["var_q_1", "var_q_2", "var_q_3", "var_q_4", "prom_movil_4", "dif_super_diesel",
             "wti_var_1", "subsidio_activo"]
CATEGORICAS = ["combustible", "direccion_actual"]
LINEA_BASE = "linea_base"
N_TEST = 10
SEMILLA = 42

COLUMNAS_PREDICCIONES = ["semana_objetivo", "combustible", "prediccion", "probabilidad",
                         "prediccion_baseline", "modelo", "version_modelo", "mlflow_run_id",
                         "fecha_generacion", "direccion_real"]
COLUMNAS_METRICAS = ["fecha_entrenamiento", "modelo", "version_modelo", "accuracy_modelo",
                     "accuracy_baseline", "f1_macro_modelo", "f1_macro_baseline",
                     "n_semanas_test", "supera_baseline", "mlflow_run_id", "es_champion"]


def _limpiar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["semana_inicio"] = pd.to_datetime(df["semana_inicio"]).dt.date
    for c in NUMERICAS:
        if c not in df:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df[df["direccion_actual"].notna()].sort_values(["semana_inicio", "combustible"])


def dividir_temporal(features: pd.DataFrame, n_test: int = N_TEST):
    """(entrenamiento, prueba, por_predecir). La prueba son las últimas `n_test` semanas con
    objetivo conocido; `por_predecir` es la última semana (objetivo nulo)."""
    df = _limpiar(features)
    conocidas = df[df["direccion_siguiente"].notna()]
    semanas = sorted(conocidas["semana_inicio"].unique())
    if len(semanas) < n_test + 4:
        raise ValueError(f"Muy pocas semanas con objetivo ({len(semanas)}) para {n_test} de prueba")
    corte = semanas[-n_test]
    entrenamiento = conocidas[conocidas["semana_inicio"] < corte]
    prueba = conocidas[conocidas["semana_inicio"] >= corte]
    ultima = df["semana_inicio"].max()
    por_predecir = df[(df["semana_inicio"] == ultima) & df["direccion_siguiente"].isna()]
    return entrenamiento, prueba, por_predecir


def _preprocesador(escalar: bool):
    num = [("imputar", SimpleImputer(strategy="median", add_indicator=True,
                                     keep_empty_features=True))]
    if escalar:
        num.append(("escalar", StandardScaler()))
    cat = OneHotEncoder(categories=[COMBUSTIBLES, CLASES], handle_unknown="ignore")
    return ColumnTransformer([("num", Pipeline(num), NUMERICAS), ("cat", cat, CATEGORICAS)])


def candidatos(semilla: int = SEMILLA) -> dict[str, Pipeline]:
    """Modelos a comparar contra la línea base (con sus hiperparámetros, para MLflow)."""
    return {
        "regresion_logistica": Pipeline([
            ("prep", _preprocesador(escalar=True)),
            ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000)),
        ]),
        "arbol_decision": Pipeline([
            ("prep", _preprocesador(escalar=False)),
            ("clf", DecisionTreeClassifier(max_depth=3, min_samples_leaf=5,
                                           class_weight="balanced", random_state=semilla)),
        ]),
    }


def metricas(y_real, y_pred) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y_real, y_pred)), 4),
        "f1_macro": round(float(f1_score(y_real, y_pred, labels=CLASES, average="macro",
                                         zero_division=0)), 4),
        "matriz_confusion": confusion_matrix(y_real, y_pred, labels=CLASES).tolist(),
    }


@dataclass
class Resultado:
    nombre: str
    metricas: dict
    modelo: Pipeline | None = None          # None = línea base
    parametros: dict = field(default_factory=dict)


@dataclass
class Comparacion:
    resultados: dict[str, Resultado]
    elegido: str
    n_semanas_test: int
    n_entrenamiento: int
    n_prueba: int
    semanas_test: tuple

    @property
    def baseline(self) -> Resultado:
        return self.resultados[LINEA_BASE]

    def supera_baseline(self, nombre: str) -> bool:
        if nombre == LINEA_BASE:
            return False
        return self.resultados[nombre].metricas["f1_macro"] > self.baseline.metricas["f1_macro"]


def entrenar_y_comparar(features: pd.DataFrame, n_test: int = N_TEST,
                        semilla: int = SEMILLA) -> Comparacion:
    """Entrena los candidatos con las semanas viejas y los compara en las últimas `n_test`."""
    entrenamiento, prueba, _ = dividir_temporal(features, n_test)
    X_tr, y_tr = entrenamiento[NUMERICAS + CATEGORICAS], entrenamiento["direccion_siguiente"]
    X_te, y_te = prueba[NUMERICAS + CATEGORICAS], prueba["direccion_siguiente"]

    resultados = {LINEA_BASE: Resultado(LINEA_BASE, metricas(y_te, prueba["direccion_actual"]))}
    for nombre, pipe in candidatos(semilla).items():
        pipe.fit(X_tr, y_tr)
        params = {k: v for k, v in pipe.named_steps["clf"].get_params().items()
                  if isinstance(v, (int, float, str, bool)) or v is None}
        resultados[nombre] = Resultado(nombre, metricas(y_te, pipe.predict(X_te)), pipe, params)

    comp = Comparacion(resultados, LINEA_BASE, n_test, len(entrenamiento), len(prueba),
                       tuple(sorted(prueba["semana_inicio"].unique())))
    mejores = sorted((r for r in resultados.values() if r.modelo is not None),
                     key=lambda r: (r.metricas["f1_macro"], r.metricas["accuracy"]), reverse=True)
    if mejores and comp.supera_baseline(mejores[0].nombre):
        comp.elegido = mejores[0].nombre
    return comp


def reentrenar_con_todo(features: pd.DataFrame, nombre: str, semilla: int = SEMILLA):
    """El elegido se vuelve a entrenar con todas las semanas con objetivo para predecir."""
    if nombre == LINEA_BASE:
        return None
    df = _limpiar(features)
    df = df[df["direccion_siguiente"].notna()]
    pipe = candidatos(semilla)[nombre]
    return pipe.fit(df[NUMERICAS + CATEGORICAS], df["direccion_siguiente"])


def predecir(features: pd.DataFrame, nombre: str, modelo: Pipeline | None,
             version_modelo: str, mlflow_run_id: str | None = None,
             ahora: datetime | None = None) -> pd.DataFrame:
    """Predicción de la semana siguiente a la última (contrato de `gold.predicciones`)."""
    _, _, ult = dividir_temporal(features, n_test=1) if len(features) else (None, None, features)
    ahora = ahora or datetime.now(timezone.utc)
    if ult is None or ult.empty:
        return pd.DataFrame(columns=COLUMNAS_PREDICCIONES)
    if modelo is None:
        pred, prob = ult["direccion_actual"].tolist(), [None] * len(ult)
    else:
        P = modelo.predict_proba(ult[NUMERICAS + CATEGORICAS])
        clases = list(modelo.classes_)
        pred = [clases[i] for i in P.argmax(axis=1)]
        prob = [round(float(p), 4) for p in P.max(axis=1)]
    return pd.DataFrame({
        "semana_objetivo": [s + pd.Timedelta(days=7) for s in pd.to_datetime(ult["semana_inicio"])],
        "combustible": ult["combustible"].tolist(),
        "prediccion": pred, "probabilidad": prob,
        "prediccion_baseline": ult["direccion_actual"].tolist(),
        "modelo": nombre, "version_modelo": version_modelo, "mlflow_run_id": mlflow_run_id,
        "fecha_generacion": ahora, "direccion_real": None,
    })[COLUMNAS_PREDICCIONES].assign(semana_objetivo=lambda d: d["semana_objetivo"].dt.date)


def unir_predicciones(anteriores: pd.DataFrame | None, nuevas: pd.DataFrame,
                      variacion: pd.DataFrame) -> pd.DataFrame:
    """Histórico de predicciones: reemplaza la de la misma semana/combustible y llena
    `direccion_real` con la dirección observada en `variacion_semanal` cuando ya se conoce."""
    partes = [p for p in (anteriores, nuevas) if p is not None and len(p)]
    if not partes:
        return pd.DataFrame(columns=COLUMNAS_PREDICCIONES)
    todo = pd.concat(partes, ignore_index=True)
    todo["semana_objetivo"] = pd.to_datetime(todo["semana_objetivo"]).dt.date
    todo = todo.drop_duplicates(["semana_objetivo", "combustible"], keep="last")
    real = variacion[["semana_inicio", "combustible", "direccion"]].copy()
    real["semana_inicio"] = pd.to_datetime(real["semana_inicio"]).dt.date
    real = dict(zip(zip(real["semana_inicio"], real["combustible"]), real["direccion"]))
    todo["direccion_real"] = pd.Series(
        [real.get((s, c)) if pd.notna(real.get((s, c))) else (d if pd.notna(d) else None)
         for s, c, d in zip(todo["semana_objetivo"], todo["combustible"], todo["direccion_real"])],
        index=todo.index, dtype=object)  # nulo = None (no NaN) en todas las versiones de pandas
    return todo[COLUMNAS_PREDICCIONES].sort_values(["semana_objetivo", "combustible"])


def filas_metricas(comp: Comparacion, version_modelo: str, run_ids: dict[str, str] | None = None,
                   ahora: datetime | None = None) -> pd.DataFrame:
    """Una fila por modelo candidato (contrato de `gold.metricas_modelo`); `es_champion` marca el
    elegido (si el elegido es la línea base, también tiene su fila)."""
    ahora = ahora or datetime.now(timezone.utc)
    base = comp.baseline.metricas
    filas = []
    for nombre, r in comp.resultados.items():
        filas.append({
            "fecha_entrenamiento": ahora, "modelo": nombre, "version_modelo": version_modelo,
            "accuracy_modelo": r.metricas["accuracy"], "accuracy_baseline": base["accuracy"],
            "f1_macro_modelo": r.metricas["f1_macro"], "f1_macro_baseline": base["f1_macro"],
            "n_semanas_test": comp.n_semanas_test, "supera_baseline": comp.supera_baseline(nombre),
            "mlflow_run_id": (run_ids or {}).get(nombre), "es_champion": nombre == comp.elegido,
        })
    return pd.DataFrame(filas, columns=COLUMNAS_METRICAS)
