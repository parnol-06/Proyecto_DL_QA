# Principios de Pruebas de Rendimiento — Referencia para Test Cases QA

## Fuente
Basado en ISTQB Performance Testing Guide, Google SRE Book, y estándares de la industria.

---

## 1. Tipos de Pruebas de Rendimiento

### 1.1 Prueba de Carga (Load Testing)
**Objetivo:** Verificar el comportamiento del sistema bajo carga esperada.

**Parámetros clave:**
- Usuarios concurrentes: definir el máximo esperado en producción
- Duración: mínimo 30 minutos para detectar degradación progresiva
- Ramp-up: incrementar usuarios gradualmente (10% cada 2 minutos)

**Métricas objetivo:**
- Tiempo de respuesta promedio: ≤ 2 segundos bajo carga normal
- Percentil 95 (P95): ≤ 3 segundos
- Percentil 99 (P99): ≤ 5 segundos
- Tasa de error: < 0.1%
- Throughput: ≥ X requests/segundo (definido por SLA)

**Ejemplo de criterio de aceptación:**
```
Con 100 usuarios concurrentes realizando búsquedas durante 30 minutos:
- Tiempo respuesta promedio ≤ 800ms
- P95 ≤ 1500ms
- Tasa de error < 0.5%
- CPU del servidor < 70%
- Memoria < 80%
```

### 1.2 Prueba de Estrés (Stress Testing)
**Objetivo:** Encontrar el punto de quiebre del sistema.

**Metodología:**
1. Aumentar carga gradualmente hasta que el sistema falle o degrade significativamente
2. Documentar el umbral exacto de falla
3. Verificar recuperación automática después del pico

**Criterio de aceptación:**
- Sistema se recupera en ≤ 60 segundos después de superar capacidad máxima
- No hay pérdida de datos durante el pico de carga
- Mensajes de error informativos (no 500 genérico)

### 1.3 Prueba de Volumen (Volume Testing)
**Objetivo:** Verificar comportamiento con grandes volúmenes de datos.

**Escenarios típicos:**
- Base de datos con 10M+ registros
- Archivos de 100MB+
- Colas de mensajes con 1M+ mensajes pendientes

**Criterio de aceptación:**
- Tiempo de query con 10M registros ≤ 500ms (con índices correctos)
- Paginación funciona correctamente con datasets grandes
- Sin memory leaks después de procesar grandes volúmenes

### 1.4 Prueba de Resistencia / Soak Testing
**Objetivo:** Detectar memory leaks y degradación progresiva.

**Duración:** Mínimo 4 horas, ideal 8-24 horas

**Criterio de aceptación:**
- Uso de memoria estable durante toda la prueba (sin crecimiento progresivo)
- Tiempo de respuesta no se degrada más del 10% después de 4 horas
- Sin errores de OutOfMemory

### 1.5 Prueba de Pico (Spike Testing)
**Objetivo:** Verificar comportamiento ante aumentos repentinos de carga.

**Metodología:**
1. Sistema en carga normal (50 usuarios)
2. Incremento súbito a 10x (500 usuarios) en 30 segundos
3. Mantener pico durante 5 minutos
4. Reducir a carga normal

**Criterio de aceptación:**
- Sistema no cae durante el pico
- Tiempo de respuesta se recupera en ≤ 2 minutos después del pico
- Auto-scaling activo en ≤ 60 segundos

---

## 2. Métricas Estándar de Rendimiento

| Métrica | Descripción | Objetivo Típico |
|---|---|---|
| Response Time | Tiempo desde request hasta respuesta completa | ≤ 2s (P50), ≤ 5s (P99) |
| Throughput | Requests por segundo exitosos | Definido por SLA |
| Error Rate | % de requests con error | < 0.1% bajo carga normal |
| CPU Usage | Uso de CPU del servidor | < 70% bajo carga normal |
| Memory Usage | Uso de RAM | < 80% bajo carga normal |
| TTFB | Time To First Byte | ≤ 200ms |
| Connection Pool | Conexiones activas a BD | < 80% del límite configurado |
| GC Pause | Tiempo de pausa por Garbage Collection (JVM/Python) | < 100ms |

---

## 3. Reglas de Oro para Test Cases de Rendimiento

### Regla 1: Siempre especificar valores numéricos concretos
**MAL:** "El sistema debe responder rápido"
**BIEN:** "Con 200 usuarios concurrentes, el P95 del endpoint /search debe ser ≤ 1500ms"

### Regla 2: Definir el entorno de prueba
Siempre especificar:
- Hardware: CPU (cores/GHz), RAM, tipo de disco (SSD/HDD)
- Red: ancho de banda, latencia
- Datos: volumen de registros en BD durante la prueba

### Regla 3: Incluir condiciones de falla
El test case debe especificar qué pasa cuando se supera el umbral:
- Circuit breaker activo
- Mensajes de error apropiados al usuario
- Logging de la degradación

### Regla 4: Definir período de observación
No es suficiente medir en el pico; medir también:
- Estado estable (primeros 5 minutos)
- Durante carga máxima
- Después de carga (recuperación)

---

## 4. Plantilla de Test Case de Rendimiento

```
ID: TC-PERF-001
Título: [Funcionalidad] bajo carga de [N] usuarios concurrentes durante [X] minutos

Precondiciones:
- Entorno de prueba configurado con [specs de hardware]
- Base de datos poblada con [N] registros de prueba
- Sistema en estado limpio (caché vacía)
- Herramienta de carga configurada: JMeter / k6 / Locust

Pasos:
1. Configurar el escenario de carga: [N] usuarios, ramp-up de [X] segundos, duración [Y] minutos
2. Iniciar la prueba de carga con el perfil definido
3. Monitorear en tiempo real: CPU, memoria, TTFB, error rate
4. Registrar métricas P50, P95, P99 cada minuto
5. Al finalizar, generar reporte con distribución de tiempos de respuesta

Resultado esperado:
- P50 ≤ [Xms], P95 ≤ [Yms], P99 ≤ [Zms]
- Error rate < [N]%
- CPU < [X]%, Memoria < [Y]%
- Sistema se mantiene estable sin memory leaks
```

---

## 5. Herramientas de Prueba de Rendimiento

| Herramienta | Tipo | Uso Recomendado |
|---|---|---|
| Apache JMeter | Load/Stress | Pruebas complejas con GUI |
| k6 | Load | Scripting en JS, CI/CD friendly |
| Locust | Load | Scripting en Python |
| Gatling | Load/Stress | Alto rendimiento, Scala/Java |
| Artillery | Load | Node.js, microservicios |
| wrk | Benchmarking | Pruebas rápidas de endpoints |

---

## 6. Criterios de Aceptación por Tipo de Sistema

### APIs REST
- P95 < 500ms para GETs simples
- P95 < 2000ms para POSTs con procesamiento
- Throughput > 500 RPS por instancia

### Búsqueda y Filtrado
- Resultados en < 500ms para datasets < 1M registros
- Paginación: primera página siempre < 200ms independiente del total

### Carga de Archivos
- Archivos de 10MB: completar en < 30 segundos
- Mostrar progreso de carga en tiempo real
- Error informativo si supera límite de tamaño

### Dashboards / Reportes
- Carga inicial < 3 segundos
- Actualizaciones en tiempo real: latencia < 1 segundo
- Datos históricos (30 días): < 5 segundos de carga
