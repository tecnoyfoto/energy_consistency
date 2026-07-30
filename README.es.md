[Read this in English](README.md)

# Energy Consistency para Home Assistant

Energy Consistency es una integración personalizada para Home Assistant que
compara el consumo eléctrico diario oficial con la energía medida localmente
durante exactamente el mismo día natural.

Su objetivo es comprobar la **coherencia energética y la calidad de los datos**.
Indica si ambas fuentes cuentan una historia coherente, pero no intenta deducir
la causa de una diferencia.

## Estado actual

La versión `0.7.2` es la primera versión preliminar pública. Ya funciona en una
instalación real de Home Assistant, dispone de pruebas automáticas, conserva el
historial verificado después de los reinicios y rechaza deliberadamente los
días parciales.

## Funciones principales

- Configuración y reconfiguración desde la interfaz de Home Assistant.
- Comparación exacta de días naturales coincidentes.
- Validación de días completos de 23, 24 y 25 horas por los cambios horarios.
- Reconstrucción local mediante estadísticas horarias de Recorder.
- Los días parciales se omiten y pueden recuperarse posteriormente.
- Recuperación automática de lecturas completas de eData publicadas con
  retraso.
- Respaldo seguro mediante el sensor oficial configurado si el historial
  interno opcional de eData no está disponible o cambia de estructura.
- Historial propio independiente de la retención de Recorder.
- Estados conservadores de aprendizaje, revisión y crítico que evitan alertas
  por un único día aislado.
- Comprobación de fuentes no disponibles, antiguas, incompletas o posiblemente
  congeladas.
- Informes mensuales CSV almacenados localmente.
- Diagnósticos descargables respetuosos con la privacidad.
- Traducciones en inglés y español.
- Insignia tipo semáforo con detalles interactivos de los días recientes.

## Requisitos

Necesitas tres entidades de Home Assistant:

1. Un sensor oficial de energía diaria en `Wh`, `kWh` o `MWh`.
2. Una entidad cuyo estado identifique la fecha representada por ese valor.
3. Un sensor local de energía acumulada con clase de dispositivo `energy` y
   clase de estado `total` o `total_increasing`.

La fuente oficial debe proporcionar información suficiente para demostrar que
el día está completo. Actualmente se admite:

- el consumo diario completo de eData;
- otro sensor oficial que exponga `last_registered_day_hours`.

Energy Consistency nunca presupone que un valor diario cualquiera esté
completo.

## Instalación

### Repositorio personalizado de HACS

1. Abre **HACS > Integraciones**.
2. Abre el menú de tres puntos y entra en **Repositorios personalizados**.
3. Añade `https://github.com/tecnoyfoto/energy_consistency` como
   **Integración**.
4. Instala **Energy Consistency**.
5. Reinicia Home Assistant.
6. Abre **Ajustes > Dispositivos y servicios > Añadir integración** y busca
   **Energy Consistency**.

### Instalación manual

Copia esta carpeta dentro de la configuración de Home Assistant:

```text
config/
  custom_components/
    energy_consistency/
```

Reinicia Home Assistant y añade la integración desde **Ajustes > Dispositivos y
servicios**.

## Configuración

En una instalación típica con eData, selecciona:

- **Consumo diario oficial:** el sensor de último consumo registrado.
- **Fecha de la lectura oficial:** la entidad de eData que contiene la fecha
  representada.
- **Energía acumulada local:** el único canal acumulado que representa el total
  de toda la vivienda.

No sumes varios canales locales salvo que la instalación física lo requiera.
Selecciona la entidad que represente el total general de la vivienda.

Cambiar el nombre conserva el historial. Cambiar cualquiera de las fuentes
inicia un historial nuevo para no mezclar mediciones diferentes.

## Modelo de estados

Clasificación diaria predeterminada:

| Estado diario | Regla |
| --- | --- |
| Correcto | Diferencia absoluta máxima de `0,5 kWh` **o** diferencia relativa máxima del `5 %` |
| Revisar | Fuera del margen correcto sin superar simultáneamente ambos umbrales críticos |
| Día crítico | Diferencia superior a `2 kWh` **y** al `15 %` |

El estado general es deliberadamente conservador:

| Estado general | Significado |
| --- | --- |
| Aprendiendo | Menos de siete días completos válidos |
| Correcto | Los días naturales completos recientes son coherentes |
| Revisar | Al menos dos días anómalos entre tres días naturales completos consecutivos |
| Crítico | Tres días críticos consecutivos o cinco días críticos en la última ventana de siete días naturales |
| Esperando | El siguiente día oficial completo todavía no está listo |
| Problema de datos | Una fuente o las estadísticas locales necesarias no son fiables |

Una fecha ausente rompe una secuencia de anomalías. Los márgenes, el periodo de
aprendizaje, el tiempo de congelación y el retraso oficial aceptado pueden
ajustarse desde las opciones. El historial se reclasifica automáticamente al
cambiar los márgenes.

## Política de días completos y datos retrasados

Una comparación solo se guarda cuando:

- la fuente oficial contiene exactamente las 23, 24 o 25 horas esperadas;
- Recorder contiene todos los intervalos horarios locales esperados;
- ambos valores energéticos son válidos y no negativos.

Si falta información en cualquiera de los lados, la fecha no se cuenta. La
integración sigue revisando días anteriores y puede incorporarla más adelante
cuando ambas fuentes estén completas.

Con eData se utiliza el historial diario cuando su estructura interna compatible
está disponible. Si esa estructura opcional falta o cambia, la integración solo
recurre al último sensor oficial configurado y continúa exigiendo todas sus
horas.

## Insignia

La integración registra su insignia automáticamente. Añade **Energy
Consistency** desde el selector de insignias o utiliza:

```yaml
type: custom:energy-consistency-badge
entity: sensor.energy_consistency_status
```

Colores:

- verde: correcto;
- naranja: revisar;
- rojo: crítico;
- gris: problema de datos;
- azul: aprendiendo o esperando.

Al pulsarla se abre el diagnóstico. Al seleccionar una fecha reciente, el
detalle superior muestra las lecturas verificadas de ese día y resalta la fila
elegida.

## Entidades

La integración crea sensores de diagnóstico para:

- estado general;
- energía oficial;
- energía local;
- diferencia con signo en kWh;
- diferencia porcentual;
- cobertura de datos locales;
- fecha de comparación;
- retraso de los datos oficiales.

## Historial e informes CSV

Las comparaciones verificadas se guardan independientemente de la retención de
Recorder. Los informes mensuales se generan en:

```text
/config/energy_consistency/reports/<config_entry_id>/
```

Incluyen lecturas, diferencias, cobertura, validación de horas oficiales,
márgenes activos, motivo de clasificación y versión del algoritmo. Un fallo al
escribir un informe se registra, pero nunca interrumpe los sensores.

## Privacidad y diagnósticos

Los diagnósticos descargables ocultan los identificadores de entidades, nombres
y lecturas energéticas absolutas. Toda la comparación se realiza localmente en
Home Assistant y no se envían datos energéticos a ningún servicio externo.

## Limitaciones conocidas

- La recuperación histórica está optimizada para eData. Otras fuentes oficiales
  pueden comparar su último día completo si proporcionan el recuento horario.
- El historial de eData utiliza una estructura interna opcional porque eData no
  expone actualmente esos días mediante una API pública de Home Assistant. Un
  respaldo protegido evita que esta dependencia bloquee comparaciones nuevas.
- La cobertura local demuestra que existen todos los intervalos horarios de
  Recorder, pero no garantiza muestras crudas ininterrumpidas dentro de cada
  hora.
- La insignia utiliza APIs del frontend de Home Assistant y puede necesitar
  mantenimiento ante futuras actualizaciones.

## Solución de problemas

- **Esperando un día oficial completo:** la fuente oficial todavía no ha
  proporcionado todas las horas esperadas.
- **Estadísticas locales incompletas:** Recorder no contiene todos los intervalos
  de esa fecha. Se omite y puede recuperarse después.
- **Problema de datos:** consulta el diagnóstico de la insignia para identificar
  fuentes no disponibles, inválidas, antiguas o posiblemente congeladas.
- **Insignia no encontrada justo después de reiniciar:** espera a que Home
  Assistant termine de arrancar y recarga completamente la página.
- **Los informes no se actualizan:** revisa el registro de Home Assistant en
  busca de un error CSV de Energy Consistency.

## Soporte

Utiliza [GitHub Issues](https://github.com/tecnoyfoto/energy_consistency/issues)
e indica la versión de Home Assistant, la versión de la integración, el texto
del diagnóstico y, cuando corresponda, los diagnósticos descargables ocultando
los datos sensibles.

## Historial de cambios

Consulta [CHANGELOG.es.md](CHANGELOG.es.md).

## Licencia

[MIT](LICENSE)
