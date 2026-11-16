-- Ejecutar con la cuenta propietaria de los recursos del Equipo 6.
-- Cuenta que utilizará los notebooks de Modelos.
GRANT USE CATALOG ON CATALOG workspace TO `sot22737@uvg.edu.gt`;

GRANT USE SCHEMA ON SCHEMA workspace.equipo_06_bronze TO `sot22737@uvg.edu.gt`;
GRANT SELECT ON SCHEMA workspace.equipo_06_bronze TO `sot22737@uvg.edu.gt`;
GRANT READ VOLUME, WRITE VOLUME ON VOLUME workspace.equipo6_bronze.crudos
TO `sot22737@uvg.edu.gt`;

GRANT USE SCHEMA, SELECT, CREATE TABLE, MODIFY ON SCHEMA workspace.equipo_06_silver
TO `sot22737@uvg.edu.gt`;
GRANT USE SCHEMA, SELECT, CREATE TABLE, MODIFY ON SCHEMA workspace.equipo_06_gold
TO `sot22737@uvg.edu.gt`;

-- Opcional para registrar el modelo en Unity Catalog.
-- El artefacto permanece en MLflow si este permiso está ausente.
-- GRANT CREATE MODEL ON SCHEMA workspace.equipo_06_gold TO `sot22737@uvg.edu.gt`;
