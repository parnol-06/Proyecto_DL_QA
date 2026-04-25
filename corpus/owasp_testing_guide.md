# OWASP Testing Guide — Referencia para Casos de Prueba de Seguridad

## Fuente
OWASP Web Security Testing Guide (WSTG) v4.2 — Adaptado para generación de test cases QA.

---

## 1. Pruebas de Autenticación

### OTG-AUTHN-001 — Testing for Credentials Transported over an Encrypted Channel
- Verificar que todas las credenciales (usuario, contraseña, token) se transmitan exclusivamente por HTTPS/TLS 1.2+
- Usar herramienta de intercepción (Burp Suite, Wireshark) para confirmar que no hay transmisión en texto plano
- **Criterio de aceptación:** 0 requests con credenciales sobre HTTP sin cifrar

### OTG-AUTHN-002 — Testing for Default Credentials
- Probar combinaciones conocidas: admin/admin, root/root, guest/guest, admin/password
- Verificar que el sistema rechaza estas combinaciones con mensaje genérico
- **Criterio de aceptación:** Sistema retorna HTTP 401 con mensaje que no revela si el usuario existe

### OTG-AUTHN-003 — Testing for Weak Lock Out Mechanism
- Realizar N intentos fallidos consecutivos (N = límite del sistema, típicamente 3-5)
- Verificar que la cuenta se bloquea temporalmente después del límite
- **Criterio de aceptación:** Cuenta bloqueada después del límite; tiempo de bloqueo ≥ 5 minutos; evento registrado en logs de auditoría

### OTG-AUTHN-004 — Testing for Bypassing Authentication Schema
- Intentar acceder a rutas protegidas sin token JWT / sin sesión activa
- Manipular cookies de sesión (eliminar, modificar valor)
- **Criterio de aceptación:** Sistema retorna HTTP 401/403 en todos los intentos de bypass

---

## 2. Pruebas de Autorización

### OTG-AUTHZ-001 — Testing Directory Traversal / File Include
- Ingresar payloads como `../../../etc/passwd`, `..%2F..%2F..%2Fetc%2Fpasswd`
- Probar en parámetros de URL, headers, cuerpo de request
- **Criterio de aceptación:** Sistema no expone archivos del sistema operativo; retorna HTTP 400

### OTG-AUTHZ-002 — Testing for Bypassing Authorization Schema (IDOR)
- Modificar IDs en requests: `/api/users/123/profile` → `/api/users/124/profile`
- Verificar que un usuario no puede acceder a recursos de otro usuario
- **Criterio de aceptación:** Sistema retorna HTTP 403 al intentar acceder a recursos ajenos

---

## 3. Pruebas de Validación de Entrada

### OTG-INPVAL-001 — Testing for Reflected Cross Site Scripting (XSS)
- Ingresar payload: `<script>alert('XSS')</script>` en campos de texto
- Probar con variaciones: `<img src=x onerror=alert(1)>`, `javascript:alert(1)`
- **Criterio de aceptación:** Script no se ejecuta; caracteres HTML son escapados correctamente

### OTG-INPVAL-005 — Testing for SQL Injection
- Ingresar payloads: `' OR '1'='1`, `'; DROP TABLE users; --`, `1' UNION SELECT null,null--`
- Probar en campos de búsqueda, login, filtros
- **Criterio de aceptación:** Sistema retorna error genérico; no revela estructura de la BD; no ejecuta el payload

### OTG-INPVAL-006 — Testing for LDAP Injection
- Ingresar: `*)(uid=*))(|(uid=*`, `*` en campos de usuario
- **Criterio de aceptación:** Sistema sanitiza la entrada; no retorna datos no autorizados

---

## 4. Pruebas de Gestión de Sesión

### OTG-SESS-001 — Testing for Cookie Attributes
- Verificar flags en cookies de sesión: `HttpOnly`, `Secure`, `SameSite=Strict`
- **Criterio de aceptación:** Todas las cookies de sesión tienen HttpOnly y Secure; SameSite configurado

### OTG-SESS-003 — Testing for Session Fixation
- Capturar session ID antes del login; completar login; verificar que el session ID cambia
- **Criterio de aceptación:** Session ID es diferente antes y después del login (rotación de sesión)

### OTG-SESS-006 — Testing for Logout Functionality
- Hacer logout y usar el token/cookie previo para acceder a recursos protegidos
- **Criterio de aceptación:** Token invalidado en el servidor; recursos retornan HTTP 401

---

## 5. Pruebas de Manejo de Errores

### OTG-ERR-001 — Testing for Error Code
- Provocar errores intencionalmente (parámetros inválidos, recursos inexistentes)
- **Criterio de aceptación:** Mensajes de error genéricos; sin stack traces; sin rutas internas del servidor

### OTG-ERR-002 — Testing for Stack Traces
- Enviar requests malformados para provocar excepciones del servidor
- **Criterio de aceptación:** La respuesta no contiene información de la tecnología, versión, ni stack trace

---

## 6. Vectores de Ataque Comunes para Test Cases

| Vector | Payload de Ejemplo | Impacto |
|---|---|---|
| SQL Injection | `' OR 1=1 --` | Acceso no autorizado a datos |
| XSS Reflejado | `<script>document.cookie</script>` | Robo de sesión |
| CSRF | Request forjada desde sitio externo | Acciones no autorizadas |
| Path Traversal | `../../../etc/passwd` | Lectura de archivos del sistema |
| Broken Auth | Token JWT modificado | Escalación de privilegios |
| IDOR | Cambiar ID en URL | Acceso a datos de otros usuarios |
| Rate Limiting Bypass | 1000 requests/segundo | DoS funcional |

---

## 7. Checklist de Seguridad para Test Cases

Para cada funcionalidad que procese datos de usuario, verificar:

- [ ] Input validation: rechaza caracteres especiales peligrosos
- [ ] Output encoding: escapa HTML en respuestas
- [ ] Authentication: endpoints protegidos requieren token válido
- [ ] Authorization: usuarios solo acceden a sus propios recursos
- [ ] Rate limiting: máximo N requests/minuto por IP/usuario
- [ ] Logging: intentos fallidos de autenticación registrados
- [ ] Sensitive data: contraseñas nunca retornadas en responses
- [ ] TLS: todos los endpoints sobre HTTPS

---

## 8. Métricas de Aceptación para Pruebas de Seguridad

- **Tiempo máximo de respuesta bajo ataque:** ≤ 2 segundos (evitar timing attacks)
- **Lockout de cuenta:** activado después de ≤ 5 intentos fallidos
- **Rotación de sesión:** token nuevo después de cada elevación de privilegios
- **Headers de seguridad requeridos:** `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`
