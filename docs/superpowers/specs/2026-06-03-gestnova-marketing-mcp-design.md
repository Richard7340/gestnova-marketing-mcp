# gestnova-marketing-mcp — Diseño v1

**Fecha:** 2026-06-03
**Autor:** Aurora + Riky
**Estado:** Diseño aprobado (pendiente de revisión de spec antes del plan de implementación)

---

## 1. Propósito

Dar al agente Gestnova de cada empresa-cliente la capacidad de **leer, analizar y
reportar** los datos de marketing de la empresa (ventas, visitas, publicidad) a
partir de las cuentas que cada cliente conecta. Es la alternativa soberana a
Windsor.ai: en vez de volcar datos a una hoja muerta, los datos se vuelven
**herramientas que un agente inteligente interpreta**, integrados en todas las
capacidades que el agente ya tiene (chat/voz, generación de docs OnlyOffice,
dashboards en la plataforma, reportes programados) y en su memoria.

**Diferencial frente a Windsor:** Windsor solo extrae datos. Aquí el mismo agente
que ya conoce la contabilidad, los documentos y el contexto de la empresa
interpreta esos datos, los cruza con todo lo demás y asiste en lenguaje natural.

## 2. Alcance

### v1 (este spec) — Lectura y análisis, como MCP autónomo
- Conectores: **Shopify** (ventas), **GA4** (visitas/tráfico), **Google Ads** (publicidad).
- Solo lectura. El agente analiza, interpreta, reporta y recomienda.
- Tool de consulta flexible para cruces a medida (no solo reportes enlatados).
- Multi-empresa: cada agente solo accede a las conexiones de SU empresa.
- Cada consulta expone un snapshot apto para la memoria del agente (continuidad).

**Entregable del v1 = el MCP en su repo, completo, probado y bien estructurado,
PERO sin cablear al agente todavía.** El MCP queda "drop-in ready": interfaz
clara, tests verdes, documentado. El wiring real al agente Gestnova se hace en
una sesión posterior (ver §6.1). Esto respeta el principio de aislamiento: el
MCP es una pieza que se entiende y prueba sola; integrarlo será un enchufe, no
una cirugía.

### Fuera del v1 (decisiones explícitas)
- **Meta (Facebook/Instagram Ads):** aplazado. App Review de Meta es lento y no
  bloquea el valor de v1. Se añade como conector posterior si hay demanda.
- **Control de plataformas (acciones de escritura):** Fase 2. Ver §7.
- **Base de datos / almacén de datos propio:** NO se construye. Ver §4.

## 3. Principios de diseño

1. **Cero invención (regla de oro).** El agente solo afirma lo que el dato real
   respalda. Si una API falla o no hay datos, dice *"no tengo datos de X para
   esas fechas"* — nunca estima ni rellena. Cada cifra que reporta lleva fuente y
   fecha.
2. **El agente es el cerebro; el MCP son los sentidos.** El MCP solo trae datos
   limpios y normalizados. Toda la inteligencia (interpretar, redactar, generar
   doc, recomendar) la pone el agente con lo que ya es.
3. **Sin DB nueva.** El histórico lo sirven las propias APIs por rango de fechas;
   el contexto/continuidad lo guarda la memoria del agente. Lo único que se
   persiste es la conexión OAuth (tokens cifrados) en la Postgres que Gestnova ya
   tiene.
4. **Conectores finos y aislados.** Cada conector (shopify/ga4/google_ads) es un
   módulo independiente con una sola responsabilidad: hablar con SU API y
   devolver datos normalizados. Si una API cambia, solo se toca ese módulo.
5. **Aislamiento por empresa.** Línea roja de seguridad: una empresa jamás accede
   a datos ni conexiones de otra.
6. **La fuente de la verdad numérica es la llamada en vivo.** La memoria del
   agente guarda snapshots e insights para continuidad y narrativa, no para
   cálculos exactos.

## 4. Arquitectura

```
Empresa-cliente → conecta sus cuentas (OAuth) → tokens cifrados en
   la Postgres que YA tiene Gestnova (Prisma) — sin base de datos nueva
                              │
        gestnova-marketing-mcp (conectores finos, llamadas en vivo)
        ├── shopify     → ventas, pedidos, productos
        ├── ga4         → visitas, tráfico, conversiones
        └── google_ads  → gasto, clics, ROAS (developer token Gestnova)
                              │
   El agente Gestnova llama estas tools en vivo cuando las necesita
                              │
   ┌──────────────┬───────────────────┬────────────────────┐
   cifra exacta    snapshot+insight     el agente entrega:
   al momento  →   a la memoria      →  chat/voz · doc OnlyOffice
   (verdad)        (continuidad)        · dashboard · reporte programado
```

**Stack:** Python + `uv`, MCP stdio, mismo patrón que `gestnova-accounting-mcp`
(src/ layout, tests/, pyproject.toml). Lo carga el agente de cada empresa.

**Modelo de credenciales multi-tenant:**
- Gestnova es la **app madre**: posee el developer token de Google Ads y las
  credenciales OAuth de cliente de cada plataforma.
- Cada empresa-cliente, desde su plataforma Gestnova, autoriza SU cuenta vía
  OAuth. El token resultante se cifra y se guarda contra su `company_id`.
- Nuevo(s) modelo(s) en la Postgres existente: `MarketingConnection`
  (`company_id`, `source`, `account_id`, `encrypted_token`, `scopes`,
  `status`, `connected_at`). Sin almacén de datos adicional.

## 5. Herramientas MCP (los "sentidos")

Todas reciben/derivan el `company_id` del agente que llama y solo operan sobre las
conexiones de esa empresa.

| Tool | Qué hace |
|---|---|
| `marketing_connect_account` | Inicia el flujo OAuth para conectar Shopify/GA4/Google Ads de la empresa |
| `marketing_list_connections` | Lista las cuentas conectadas de la empresa y su estado |
| `marketing_sales` | Ventas/pedidos/productos por rango de fechas (Shopify) |
| `marketing_traffic` | Visitas, sesiones, fuentes de tráfico, conversiones (GA4) |
| `marketing_ads` | Gasto, clics, impresiones, ROAS de campañas (Google Ads) |
| `marketing_overview` | Resumen unificado de las 3 fuentes para un periodo (alimenta el reporte programado) |
| `marketing_query` | **Consulta flexible**: `source`, métricas, dimensiones, fechas, filtros. Permite cruces a medida ("ventas por producto los martes", "tráfico por ciudad que convirtió") sin estar limitado a reportes enlatados |

**Contrato de salida (todas las tools de datos):** devuelven datos normalizados +
metadatos obligatorios — `source`, `account_id`, `date_range`, `fetched_at`.
Estos metadatos son los que garantizan el principio de cero invención: el agente
siempre sabe de dónde y de cuándo es cada cifra.

**Manejo de errores/sin datos:** si la API falla o no hay datos, la tool devuelve
un estado explícito (`status: "no_data" | "error"` + motivo). El agente NUNCA
debe inventar; debe comunicar la ausencia de dato.

## 6. Integración con las capacidades del agente (diseñada, cableada en fase posterior)

El MCP **no inventa una vía de entrega nueva**. Expone datos; el agente decide con
sus capacidades actuales:
- **Conversacional** (chat/voz/WhatsApp): "¿cómo van las ventas esta semana?"
- **Documentos** (OnlyOffice Word/Excel/PDF): genera el reporte como artefacto.
- **Dashboard** en la plataforma Gestnova (AppManifest + webOS existente).
- **Reporte programado** (p.ej. cada lunes) usando `marketing_overview`.

Tras cada consulta relevante, el agente escribe un **snapshot + insight** en su
memoria (en Aurora: QNet/Memory Hub; en cada cliente: la memoria de su agente),
para que el dato pase a formar parte de lo que el agente sabe y recuerda de la
empresa, junto con su contabilidad y demás contexto.

### 6.1 El cableado al agente es una fase posterior

El v1 **deja el MCP listo pero NO lo conecta al agente.** La integración real
—registrar las tools en el agente Gestnova, exponerlas en el chat y la voz del
webOS, y conectar el MCP al kernel del webOS a través de los conectores
existentes— se hace en una sesión aparte, una vez el MCP esté probado y estable.

Para que ese enchufe sea trivial cuando llegue, el v1 debe entregar:
- Contrato de tools estable y documentado (nombres, inputs, outputs, metadatos).
- Arranque del servidor MCP por stdio igual que los demás `gestnova-*-mcp`
  (mismo patrón de carga que el agente ya usa para accounting/legal/etc.).
- README de integración: cómo se registraría en el agente y en el kernel del
  webOS cuando se decida cablear.
- Sin dependencias del runtime del agente: el MCP no importa nada del agente;
  solo el agente importará/registrará el MCP en el futuro.

## 7. Fase 2 (documentada, no en v1) — Control de plataformas

Capa de **acciones de escritura** (pausar/activar campaña, cambiar presupuesto,
publicar, editar producto). Se construye plataforma a plataforma, **después** de
que la lectura sea sólida y confiable, porque:
- Requiere **write scopes** → App Review mucho más estricto de Google/Meta.
- Toca **dinero y reputación reales**: un error gasta dinero o publica algo malo.
- Cada acción es a medida por plataforma.

**Línea roja inamovible:** toda acción que gaste dinero o publique requiere
**confirmación humana explícita**. El agente propone, el humano aprueba. El
agente nunca mueve dinero ni publica por su cuenta.

## 8. Restricciones externas conocidas (sequencing)

- **Shopify y GA4:** construibles ya. OAuth estándar, sin permisos especiales.
- **Google Ads:** requiere developer token con **Basic/Standard access aprobado**
  (no modo *test*, que solo lee cuentas de prueba). Hay que verificar el nivel de
  acceso del token de Gestnova al construir el conector.
- **Meta:** fuera de v1 por el coste de App Review.

## 9. Criterios de éxito (v1 — MCP autónomo, sin cablear al agente)

1. El MCP arranca por stdio igual que los demás `gestnova-*-mcp` y lista sus
   tools, sin depender del runtime del agente.
2. Una empresa conecta su Shopify y GA4 vía OAuth; el token cifrado se guarda
   contra su `company_id`.
3. Invocando las tools directamente (tests/cliente MCP de prueba), se obtienen
   cifras reales de ventas y visitas por rango de fechas, cada una con sus
   metadatos (`source`, `account_id`, `date_range`, `fetched_at`).
4. `marketing_query` resuelve al menos un cruce a medida no contemplado por los
   reportes enlatados.
5. Aislamiento verificado: una llamada con el `company_id` de la empresa A no
   puede leer datos ni conexiones de B.
6. Ante fallo de API o ausencia de datos, la tool devuelve `status: no_data |
   error` con motivo — nunca cifras inventadas.
7. README de integración presente: documenta cómo se cableará al agente y al
   kernel del webOS en la fase posterior.

> El reporte en doc OnlyOffice y la entrega conversacional/voz son capacidades
> del agente y se validan en la fase de integración posterior, no en el v1.
