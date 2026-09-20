# Historial de cambios

Este archivo documenta los cambios destacados de Energy Consistency.

## [0.9.0] - 2026-09-20

### Añadido

- Nombres editables e interruptores persistentes de inclusión para los dos
  contadores locales.
- Pantalla visible **Configurar > Contadores locales** con selección, inclusión
  y calibración de cada fuente.
- Calibración opcional por contador, conservando valores diarios brutos y
  ajustados.
- Motivo de selección, desacuerdo, diferencia entre fuentes, nombres, estado de
  inclusión y calibración en diagnósticos e informes CSV.

### Cambiado

- El desacuerdo entre dos contadores completos e incluidos conserva la lectura
  principal, guarda el día y muestra una advertencia en vez de bloquearlo como
  problema de datos.
- Excluir una fuente solo afecta a la coherencia y al respaldo. El histórico de
  Recorder y los valores brutos diarios permanecen intactos.
- La insignia interactiva muestra nombres, valores brutos y ajustados, inclusión,
  diferencia entre fuentes y motivo de selección.

## [0.8.0] - 2026-09-14

### Añadido

- Contador local de respaldo opcional y prioritario; las lecturas se seleccionan
  y nunca se suman.
- Conmutación automática para días incompletos, inválidos, no disponibles o
  congelados del contador principal.
- Problema de datos conservador cuando dos contadores completos no coinciden.
- Detección configurable de congelación en días completos.

### Cambiado

- El historial se conserva al añadir, retirar o reordenar contadores locales.
- Cada comparación nueva guarda el contador elegido, el motivo de respaldo, las
  lecturas, la cobertura y las rachas de horas a cero.
- Las configuraciones existentes de un solo contador se migran sin perder datos.

## [0.7.3] - 2026-07-31

### Corregido

- Registra la insignia interactiva como recurso persistente de Lovelace para
  que las conexiones remotas de Android no dependan de una caché separada del
  HTML inicial.
- Mantiene el registro automático como módulo adicional para las instalaciones
  que gestionan los recursos de Lovelace mediante YAML.

## [0.7.2] - 2026-07-30

Primera versión pública.

### Añadido

- Configuración, reconfiguración y márgenes ajustables desde la interfaz.
- Comparación exacta de días completos mediante horas oficiales y estadísticas
  horarias de Recorder, incluidos los días de 23 y 25 horas.
- Estados conservadores de aprendizaje, revisión, crítico, espera y salud de
  datos.
- Historial persistente, recuperación de eData e informes mensuales CSV.
- Comprobaciones de disponibilidad, antigüedad, integridad y congelación.
- Diagnósticos descargables respetuosos con la privacidad.
- Traducciones en inglés y español.
- Insignia interactiva con selección de fechas recientes.
- Icono local para la integración personalizada.
- Pruebas automáticas del motor, persistencia y compatibilidad con eData.

### Seguridad y fiabilidad

- Los días oficiales o locales parciales nunca se consideran discrepancias.
- Los días ausentes rompen las secuencias de anomalías y pueden recuperarse.
- El último resultado verificado se conserva mientras Home Assistant arranca.
- Si el historial interno opcional de eData falta o es incompatible, solo se usa
  como respaldo un sensor oficial configurado que demuestre estar completo.
