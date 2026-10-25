[Read this in English](README.md)

# Energy Consistency para Home Assistant

Energy Consistency es una integración personalizada para Home Assistant que
compara el consumo eléctrico diario oficial con la energía medida localmente
durante exactamente el mismo día natural.

Su objetivo es comprobar la **coherencia energética y la calidad de los datos**.
Indica si ambas fuentes cuentan una historia coherente, pero no intenta deducir
la causa de una diferencia.

## Estado actual

La versión `0.9.1` es la versión preliminar pública actual. Ya funciona en una
instalación real de Home Assistant, dispone de pruebas automáticas, conserva el
historial verificado después de los reinicios y rechaza deliberadamente los
días parciales.

## Funciones principales

- Configuración y reconfiguración desde la interfaz de Home Assistant.
- Un contador local principal y otro de respaldo opcional; nunca se suman.
- Nombres editables e interruptores de inclusión para cada contador local.
- Los contadores excluidos conservan su histórico y valores diarios, pero no
  participan en la coherencia ni en el cambio automático.
- Calibración opcional por contador, conservando por separado el valor bruto y
  el ajustado.
- Conmutación diaria si el contador principal está incompleto o congelado.
- Un desacuerdo genera una advertencia y guarda el valor principal en vez de
  descartar el día completo.
- Cambio de contador y prioridad sin perder el historial verificado.
- La reconfiguración sigue disponible aunque un contador configurado esté
  temporalmente no disponible o en estado desconocido.
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

Necesitas tres entidades de Home Assistant y puedes configurar una cuarta:

1. Un sensor oficial de energía diaria en `Wh`, `kWh` o `MWh`.
2. Una entidad cuyo estado identifique la fecha representada por ese valor.
3. Un sensor local de energía acumulada con clase de dispositivo `energy` y
   clase de estado `total` o `total_increasing`.
4. Opcionalmente, un segundo sensor local acumulado utilizado solo como respaldo.

La fuente oficial debe proporcionar información suficiente para demostrar que
el día está completo. Actualmente se admite:

- el consumo diario completo de eData;
- otro sensor oficial que exponga `last_registered_day_hours` o `last_day_delta_h`.

Energy Consistency nunca presupone que un valor diario cualquiera esté
completo.

## Instalación

### Instalación manual desde GitHub (descarga directa)

1. Descarga [energy_consistency-0.9.1.zip](https://github.com/tecnoyfoto/energy_consistency/releases/download/0.9.1/energy_consistency-0.9.1.zip) desde la [versión 0.9.1](https://github.com/tecnoyfoto/energy_consistency/releases/tag/0.9.1).
2. Descomprime el ZIP en tu ordenador. Dentro encontrarás la carpeta `custom_components/energy_consistency`.
3. Copia **solo la carpeta `energy_consistency`** dentro de `custom_components` en la carpeta de configuración de Home Assistant. Crea `custom_components` si no existe. El resultado debe ser:

```text
config/
  custom_components/
    energy_consistency/
      __init__.py
      manifest.json
      ...
```

4. Reinicia Home Assistant.
5. Abre **Ajustes > Dispositivos y servicios > Añadir integración**, busca **Energy Consistency** y selecciona tus fuentes.

**Si ya la tienes instalada:** sustituye los archivos de `custom_components/energy_consistency` por los de la nueva versión y reinicia. No elimines la integración desde la interfaz ni borres `.storage` o los informes: así mantendrás la configuración y el historial. No copies la carpeta exterior del ZIP dentro de `energy_consistency`, ni reemplaces toda tu carpeta `custom_components`.

No se necesitan credenciales ni tokens para Energy Consistency. La integración utiliza las entidades que ya tienes configuradas en Home Assistant. Si usas eData como fuente oficial, instálalo y configúralo primero.

### Opcional: repositorio personalizado de HACS

No necesitas esperar a que aparezca en el catálogo predeterminado de HACS. Puedes añadir el repositorio manualmente:

1. Abre **HACS > Integraciones**.
2. Abre el menú de tres puntos y entra en **Repositorios personalizados**.
3. Añade `https://github.com/tecnoyfoto/energy_consistency` como **Integración**.
4. Instala **Energy Consistency** y reinicia Home Assistant.
5. Añade la integración desde **Ajustes > Dispositivos y servicios**.

## Configuración

En una instalación típica con eData, selecciona:

- **Consumo diario oficial:** el sensor de último consumo registrado.
- **Fecha de la lectura oficial:** la entidad de eData que contiene la fecha
  representada.
- **Energía acumulada local:** el único canal acumulado que representa el total
  de toda la vivienda.

Los dos contadores locales deben representar la misma magnitud física de toda la
vivienda. El respaldo sustituye al principal solo cuando hace falta; sus lecturas
nunca se suman.

Cambiar el nombre, los contadores locales o su prioridad conserva el historial
verificado. Cambiar una fuente oficial inicia un historial nuevo. Cada registro
nuevo guarda qué contador local se utilizó y si hubo conmutación.

Abre **Ajustes > Dispositivos y servicios > Coherencia energética > Configurar
> Contadores locales** para seleccionar y nombrar cada contador, definir su
factor de calibración o excluirlo de la coherencia. La integración también crea
un interruptor de inclusión por contador. Apagarlo no desconecta el contador
físico ni impide que Home Assistant continúe registrando su sensor.

Los factores de calibración parten de `1,000`. Solo afectan al valor ajustado
utilizado para la coherencia; el consumo diario bruto continúa disponible en el
diagnóstico y en los informes CSV.

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


## Compatibilidad y actualizaciones (0.9.1)

La fuente oficial es configurable: no se incluyen entidades, credenciales ni datos de una vivienda concreta. eData es opcional. La compatibilidad moderna se ha comprobado con eData 2026.10.4; se conserva el adaptador antiguo y un respaldo seguro mediante el sensor del último día completo. El acceso al historial de eData es opcional y depende de su API interna, por lo que no se garantiza compatibilidad con versiones futuras.

Al detectar el cambio de identidad de eData de `last_registered_day_kwh` a `last_day_kwh`, la integración migra automáticamente a la nueva entidad del **mismo suministro y entrada de eData**, aunque Home Assistant le asigne `_2`. Esa migración conserva las comparaciones; no selecciona otro suministro por similitud de nombre. Un cambio manual a otra fuente oficial sigue iniciando un historial nuevo.

Las estadísticas locales se solicitan a Recorder en kWh. Cambiar la unidad visible del sensor entre Wh, kWh y MWh no altera la interpretación del historial. Recorder debe estar habilitado e incluir los contadores seleccionados. Una hora presente en Recorder no demuestra que hubiera muestras continuas durante toda esa hora.

La recuperación automática revisa los últimos 14 días, o el retraso oficial máximo configurado si es mayor. Solo guarda días completos con datos locales disponibles. El historial propio conserva hasta 730 comparaciones. Los cambios de inclusión, prioridad y calibración se aplican a las nuevas comparaciones; las ya verificadas mantienen el contador y la calibración utilizados en su momento, salvo que una corrección oficial o una nueva versión del algoritmo de medida requiera recalcular un día disponible.

Para actualizar desde HACS, instala la nueva versión y reinicia Home Assistant. No elimines y vuelvas a añadir la integración: eliminarla borra su historial e informes. Si la insignia conserva el aspecto anterior, recarga el navegador; su recurso lleva la versión para renovar la caché. El proyecto se instala como repositorio personalizado de HACS; eso no implica que forme parte del catálogo predeterminado de HACS.

## Diagnóstico y soporte seguro

Cuando una fuente no está disponible, la insignia identifica la entidad y su estado. Las lecturas anteriores siguen visibles con una indicación de que pertenecen a la última comparación guardada. Un contador de respaldo excluido no se presenta como una fuente que haya que reparar.

Los diagnósticos descargables ocultan el título personalizado, los nombres, los identificadores de entidad, los consumos y las diferencias absolutas y relativas que permitirían reconstruirlos. Mantienen fechas, estados, cobertura y umbrales para facilitar el soporte. Los CSV son exportaciones privadas: contienen consumos y nombres; no los adjuntes a una incidencia pública sin revisarlos. Los nombres que una hoja de cálculo podría interpretar como fórmulas se exportan como texto.

Antes de pedir ayuda, comprueba la disponibilidad de las fuentes, que Recorder incluye los contadores y que eData ha publicado todas las horas del día. Incluye las versiones de Home Assistant, Energy Consistency y la fuente oficial, el motivo del aviso y, si hace falta, los diagnósticos revisados. No publiques tokens, contraseñas, configuraciones completas ni capturas con datos personales.

La fecha oficial debe identificar el mismo día natural y zona horaria que Home Assistant. Si la fuente expresa otra fecha, normalízala mediante un sensor de origen o plantilla antes de seleccionarla. Consulta [la auditoría pública](AUDIT.md) para conocer las comprobaciones y sus límites.
