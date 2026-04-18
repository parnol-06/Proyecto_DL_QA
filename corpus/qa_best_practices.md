# Buenas Prácticas en QA y Diseño de Casos de Prueba

## 1. Fundamentos del Diseño de Casos de Prueba

Un caso de prueba bien diseñado debe ser atómico, repetible, independiente y trazable al requisito que valida. La calidad de una suite de pruebas no se mide solo por la cantidad de casos, sino por la diversidad de escenarios cubiertos y la precisión de sus criterios de éxito.

### Características de un caso de prueba de calidad

- **Título descriptivo**: debe comunicar qué se prueba y bajo qué condición. Evitar títulos genéricos como "Probar login".
- **Precondiciones explícitas**: el estado del sistema antes de ejecutar el caso debe estar completamente definido.
- **Pasos numerados y específicos**: cada paso debe ser una acción concreta con datos de entrada precisos. Ejemplo: "Ingresar el correo usuario@dominio.com en el campo Email".
- **Resultado esperado medible**: debe ser verificable sin ambigüedad. En pruebas de rendimiento, incluir tiempos máximos en milisegundos o segundos.
- **Datos de prueba definidos**: especificar los valores exactos a usar, no descripciones vagas como "un email inválido".

## 2. Técnicas de Diseño

### 2.1 Partición de Equivalencia

Divide el dominio de entrada en clases donde el sistema se comporta igual para todos los valores. Para cada clase se diseña al menos un caso:

- **Clases válidas**: entradas que el sistema debe aceptar. Ejemplo: contraseña de 8-20 caracteres.
- **Clases inválidas**: entradas que el sistema debe rechazar. Ejemplo: contraseña de 3 caracteres, contraseña vacía, contraseña de 100 caracteres.

### 2.2 Análisis de Valores Límite

Complementa la partición de equivalencia probando los valores en los bordes de cada clase:

- El valor mínimo exacto (ej: 8 caracteres)
- El valor mínimo menos uno (ej: 7 caracteres)
- El valor máximo exacto (ej: 20 caracteres)
- El valor máximo más uno (ej: 21 caracteres)

Esta técnica detecta errores de condiciones de frontera que son muy comunes.

### 2.3 Tablas de Decisión

Útil cuando múltiples condiciones determinan el comportamiento. Se construye una tabla con todas las combinaciones de condiciones y el resultado esperado. Ejemplo para login:

| Usuario existe | Contraseña correcta | Cuenta bloqueada | Resultado |
|---|---|---|---|
| Sí | Sí | No | Acceso concedido |
| Sí | No | No | Error credenciales |
| Sí | No | Sí | Error cuenta bloqueada |
| No | — | — | Error usuario no encontrado |

### 2.4 Pruebas de Transición de Estado

Para funcionalidades con estados (ej: carrito, pedidos, sesiones), diseñar casos que cubran todas las transiciones válidas e inválidas entre estados.

## 3. Categorías de Prueba

### 3.1 Pruebas Funcionales

Verifican que el sistema hace lo que debe hacer según los requisitos.

- **Camino feliz (Happy Path)**: flujo principal sin errores, con datos válidos y condiciones normales.
- **Casos negativos**: entradas inválidas, datos fuera de rango, flujos alternativos de error.
- **Casos límite**: valores en los bordes de las restricciones del sistema.
- **Pruebas de integración**: interacción entre módulos, APIs externas, bases de datos.

### 3.2 Pruebas de Seguridad

Validan que el sistema protege datos y recursos contra accesos no autorizados y ataques maliciosos.

**Inyección SQL**: intentar modificar consultas de base de datos mediante inputs maliciosos.
- Ejemplo de payload: `' OR '1'='1` en campos de login
- Ejemplo de payload: `'; DROP TABLE users; --` en campos de búsqueda
- El sistema debe sanitizar entradas y usar consultas parametrizadas.

**Cross-Site Scripting (XSS)**: inyectar scripts en campos de texto que se renderizan en el navegador.
- Payload básico: `<script>alert('XSS')</script>`
- El sistema debe escapar caracteres especiales al renderizar contenido de usuario.

**Autenticación y autorización**:
- Intentar acceder a recursos protegidos sin autenticación → debe devolver 401
- Intentar acceder a recursos de otro usuario → debe devolver 403
- Verificar que los tokens expiran correctamente
- Probar fuerza bruta: N intentos fallidos deben bloquear la cuenta

**Exposición de datos sensibles**:
- Las contraseñas no deben aparecer en logs ni en respuestas de API
- Los tokens no deben ser predecibles

### 3.3 Pruebas de Rendimiento

Validan que el sistema responde en tiempos aceptables bajo distintas condiciones de carga. Los criterios deben ser cuantitativos:

- **Tiempo de respuesta máximo**: Ejemplo: el login debe completarse en menos de 2 segundos bajo carga normal.
- **Prueba de carga**: comportamiento con N usuarios concurrentes. Ejemplo: 100 usuarios simultáneos generando reportes.
- **Prueba de estrés**: comportamiento por encima de la capacidad diseñada. Ejemplo: 500 usuarios concurrentes.
- **Prueba de volumen**: comportamiento con grandes cantidades de datos. Ejemplo: búsqueda en base de datos con 1,000,000 registros.

Métricas clave: tiempo de respuesta percentil 95 (P95), throughput (req/s), tasa de error bajo carga.

### 3.4 Pruebas de Usabilidad

Verifican que la interfaz es intuitiva y accesible:

- Los mensajes de error son claros y orientan al usuario sobre cómo corregir el problema.
- Los campos obligatorios están claramente marcados.
- La aplicación funciona con teclado (navegación por Tab, Enter en formularios).
- Los tiempos de espera tienen indicadores visuales (spinner, barra de progreso).
- Los formularios preservan los datos ingresados si hay un error de validación.

### 3.5 Pruebas de Compatibilidad

Validan el funcionamiento en diferentes entornos:

- Navegadores: Chrome, Firefox, Safari, Edge (últimas 2 versiones)
- Dispositivos: desktop (1920x1080, 1366x768), tablet (768x1024), móvil (375x667)
- Sistemas operativos: Windows 10/11, macOS, iOS, Android
- Conexiones de red: fibra, 4G, 3G (simular con throttling)

## 4. Métricas de Cobertura

### ¿Qué es una buena cobertura?

La cobertura no es solo un porcentaje, sino la garantía de que los escenarios de mayor riesgo están cubiertos. Una suite con 80% de cobertura de requisitos pero que omite todos los casos de seguridad es menos valiosa que una con 60% que cubre los flujos críticos de negocio.

**Cobertura mínima recomendada:**
- 100% de caminos felices para funcionalidades críticas
- Al menos 2 casos negativos por cada validación de negocio
- Al menos 1 caso de seguridad por cada endpoint que maneja datos sensibles
- Al menos 1 caso de rendimiento por cada operación que tarda más de 1 segundo

### Áreas frecuentemente olvidadas

- Comportamiento tras expiración de sesión
- Mensajes de error del servidor (errores 500)
- Comportamiento sin conexión a internet (apps móviles)
- Datos con caracteres especiales (acentos, emojis, caracteres Unicode)
- Campos con el tamaño máximo exacto de caracteres

## 5. Priorización de Casos de Prueba

Asignar prioridad considerando:

- **Alta**: caminos felices de funcionalidades core, casos de seguridad, flujos de pago
- **Media**: casos límite, flujos alternativos frecuentes, compatibilidad en navegadores principales
- **Baja**: casos edge poco probables, compatibilidad en navegadores minoritarios, optimizaciones de usabilidad

La prioridad determina el orden de ejecución en regresión y qué se ejecuta en ciclos cortos de CI/CD.
