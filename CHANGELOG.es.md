# Historial de cambios

Este archivo documenta los cambios destacados de Energy Consistency.

## [0.7.2] - 2026-07-30

Primera versión preliminar pública.

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
