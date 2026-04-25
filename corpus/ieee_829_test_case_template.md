# IEEE 829 — Estándar para Documentación de Pruebas de Software

## Fuente
IEEE Standard 829-2008 for Software and System Test Documentation. Adaptado para generación automatizada de test cases QA.

---

## 1. Estructura IEEE 829 para Test Cases

### 1.1 Identificador del Test Case
Código único que permita trazabilidad desde el requisito hasta el defecto.

**Formato recomendado:** `[PROYECTO]-[MÓDULO]-[TIPO]-[NÚMERO]`
- Ejemplo: `ECOMM-AUTH-SEC-001` (E-commerce, Autenticación, Seguridad, caso 1)
- Tipos: `FUNC` (funcional), `SEC` (seguridad), `PERF` (rendimiento), `INT` (integración), `UI` (interfaz)

### 1.2 Elementos Obligatorios de un Test Case

```
1. Identificador único (ID)
2. Trazabilidad al requisito o user story
3. Objetivo del test case
4. Prerrequisitos y precondiciones
5. Datos de entrada (inputs)
6. Pasos de ejecución (detallados y reproducibles)
7. Resultado esperado (criterio de aceptación)
8. Resultado real (se completa durante ejecución)
9. Estado: Aprobado / Fallido / Bloqueado / No ejecutado
10. Prioridad: Alta / Media / Baja
11. Tipo: Funcional / No Funcional / Regresión / Humo
```

---

## 2. Guía para Escribir Pasos de Prueba Efectivos

### 2.1 Principios de Pasos Bien Escritos

**Principio 1 — Atomicidad:** Cada paso debe describir UNA acción
- **MAL:** "Ir al formulario de login, ingresar credenciales y hacer clic en el botón"
- **BIEN:** 
  1. Navegar a `https://app.example.com/login`
  2. Ingresar en el campo "Email": `usuario.prueba@empresa.com`
  3. Ingresar en el campo "Contraseña": `Contr@sena2024!`
  4. Hacer clic en el botón "Iniciar sesión"

**Principio 2 — Especificidad:** Usar datos concretos, no genéricos
- **MAL:** "Ingresar un email válido"
- **BIEN:** "Ingresar en el campo Email el valor: `qa.tester@dominio.com`"

**Principio 3 — Reproducibilidad:** Cualquier persona puede ejecutar el test sin ambigüedad
- **MAL:** "Verificar que la respuesta es correcta"
- **BIEN:** "Verificar que la respuesta HTTP es 200 y el body contiene el campo `user.id` con un UUID válido"

**Principio 4 — Valores cuantitativos para casos no funcionales**
- **MAL:** "El sistema debe responder rápido"
- **BIEN:** "Verificar que el tiempo de respuesta es ≤ 800 milisegundos (medido con Postman o DevTools Network)"

---

## 3. Categorías de Test Cases por Tipo de Prueba

### 3.1 Camino Feliz (Happy Path)
Flujo principal cuando todo funciona correctamente con datos válidos.

**Características:**
- Datos de entrada 100% válidos y dentro de límites
- Usuario con permisos correctos
- Sistema en estado normal

**Ejemplo:**
```
Título: Login exitoso con credenciales válidas y cuenta activa
Input: Email=usuario@empresa.com, Password=ValidPass2024!
Resultado esperado: Redirección a /dashboard con HTTP 200; token JWT en header Authorization
```

### 3.2 Caso Límite (Boundary / Edge Case)
Pruebas en los límites exactos de los valores permitidos.

**Valores a probar:**
- Mínimo exacto (ej: contraseña de exactamente 8 caracteres)
- Máximo exacto (ej: nombre de 255 caracteres)
- Mínimo - 1 (ej: contraseña de 7 caracteres → debe fallar)
- Máximo + 1 (ej: nombre de 256 caracteres → debe fallar)
- Valores vacíos, nulos, espacios en blanco

**Ejemplo:**
```
Título: Registro con contraseña de exactamente 8 caracteres (límite mínimo)
Input: Password="AbcD1!#@" (8 caracteres exactos)
Resultado esperado: Registro exitoso; contraseña acepta el límite mínimo
```

### 3.3 Caso Negativo (Negative Testing)
Verificar que el sistema rechaza entradas inválidas apropiadamente.

**Tipos de entradas inválidas:**
- Formato incorrecto (email sin @, fecha inválida)
- Tipo de dato incorrecto (texto donde se espera número)
- Valores fuera de rango (cantidad negativa, porcentaje > 100)
- Caracteres no permitidos

**Ejemplo:**
```
Título: Intento de login con contraseña incorrecta
Input: Email=usuario@empresa.com, Password=ContraseñaIncorrecta
Resultado esperado: HTTP 401; mensaje "Credenciales incorrectas" (sin indicar si el email existe)
```

### 3.4 Seguridad (Security Testing)
Verificar que el sistema resiste ataques conocidos.

**Siempre especificar el vector de ataque:**
```
Título: Resistencia a inyección SQL en campo de búsqueda
Input: query="' OR '1'='1' --"
Vector de ataque: SQL Injection en parámetro de búsqueda
Resultado esperado: HTTP 400; sin datos no autorizados; payload sanitizado en logs
```

### 3.5 Rendimiento (Performance Testing)
Verificar tiempos de respuesta bajo condiciones de carga.

**Siempre incluir:**
- Número concreto de usuarios concurrentes
- Duración de la prueba
- Métricas con valores numéricos (P50, P95, P99)

```
Título: Búsqueda de productos con 50 usuarios concurrentes durante 5 minutos
Condición: 50 usuarios realizando búsquedas simultáneas
Resultado esperado: P95 ≤ 1200ms; error rate < 0.5%; CPU < 60%
```

### 3.6 Usabilidad (Usability Testing)
Verificar que la interfaz es intuitiva y accesible.

**Criterios medibles:**
- Tiempo en completar tarea: ≤ X segundos
- Número de clics para completar tarea: ≤ N clics
- Mensajes de error comprensibles sin conocimiento técnico

```
Título: Usuario nuevo completa registro sin instrucciones adicionales
Criterio: Usuario completa el registro en ≤ 3 minutos con ≤ 0 errores de UX
Resultado esperado: Formulario se autocompleta donde es posible; labels claros; mensajes de validación en tiempo real
```

### 3.7 Compatibilidad (Compatibility Testing)
Verificar funcionamiento en diferentes entornos.

```
Título: Login funciona en Chrome 120+, Firefox 120+, Safari 17+, Edge 120+
Entornos: Chrome 120 / Windows 11, Firefox 120 / macOS, Safari 17 / iOS 17, Edge 120 / Android 14
Resultado esperado: Funcionalidad idéntica en todos los navegadores; sin errores de consola JS
```

---

## 4. Plantilla Completa IEEE 829

```
ID: [PROYECTO]-[MÓDULO]-[TIPO]-[NNN]
Título: [Acción] + [condición] + [resultado observable]
Trazabilidad: [US-XX] / [REQ-XX]
Tipo de prueba: Funcional | No Funcional | Integración | UI | API | Seguridad | Rendimiento
Prioridad: Alto | Medio | Bajo
Estado: No ejecutado | En ejecución | Aprobado | Fallido | Bloqueado

PRECONDICIONES:
  1. [Estado del sistema requerido]
  2. [Datos de prueba necesarios]
  3. [Permisos / roles del usuario de prueba]

DATOS DE ENTRADA:
  - Campo1: [valor exacto]
  - Campo2: [valor exacto]

PASOS:
  1. [Acción atómica con elemento UI o endpoint específico]
  2. [Acción atómica...]
  3. [Verificación de estado intermedio]
  4. [Acción atómica...]
  5. [Verificación final]

RESULTADO ESPERADO:
  [Estado observable, medible y específico del sistema después de ejecutar los pasos]
  - HTTP status: [código]
  - UI: [estado visible exacto]
  - BD: [cambio esperado en datos si aplica]
  - Tiempo: [si aplica, valor en ms]

RESULTADO REAL: [Se completa durante ejecución]
DEFECTO REPORTADO: [ID del bug si aplica]
```

---

## 5. Trazabilidad Requisito → Test Case → Defecto

La trazabilidad es un requisito IEEE 829. Para cada test case:

```
Requisito / User Story
       ↓
  Test Case(s)
       ↓
  Ejecución → Resultado
       ↓
  Defecto (si falla) → Con ID y prioridad
```

**Matriz de trazabilidad mínima:**

| User Story | Test Cases | Cobertura |
|---|---|---|
| US-01: Login | TC-001, TC-002, TC-003 | Happy path, negativo, seguridad |
| US-02: Registro | TC-004, TC-005 | Happy path, límite |

---

## 6. Criterios de Cobertura de Pruebas

### Cobertura Mínima Aceptable
- **Funciones críticas** (login, pago, datos sensibles): 100% de happy path + casos negativos + seguridad
- **Funciones normales**: 80% de escenarios relevantes
- **Funciones de baja criticidad**: 60% de escenarios relevantes

### Distribución Recomendada de Test Cases
- 30-40% Happy Path
- 25-30% Casos Negativos
- 15-20% Casos Límite
- 10-15% Seguridad
- 5-10% Rendimiento
- 5-10% Usabilidad / Compatibilidad
