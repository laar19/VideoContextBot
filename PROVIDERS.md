# 🔄 Proveedores Compatibles con VideoContextBot

VideoContextBot usa el SDK de OpenAI, que es compatible con múltiples proveedores de APIs de Whisper.

## 🚀 Proveedores Soportados

### 1. Groq (Recomendado) ⭐

**Ventajas:**
- ✅ Gratis (con límites generosos)
- ✅ Muy rápido (inferencia en tiempo real)
- ✅ Modelos de última generación
- ✅ Sin necesidad de tarjeta de crédito para empezar

**Configuración:**
```env
OPENAI_API_KEY=gsk_tu-api-key-aqui
OPENAI_BASE_URL=https://api.groq.com/openai/v1
WHISPER_MODEL=whisper-large-v3
```

**Obtener API Key:**
1. Ve a https://console.groq.com/
2. Regístrate (gratis)
3. Crea una API Key en "API Keys"
4. Copia y pega en `.env`

**Modelos disponibles:**
- `whisper-large-v3` - Mejor calidad, más lento
- `whisper-large-v3-turbo` - Más rápido, buena calidad

---

### 2. OpenAI Oficial

**Ventajas:**
- ✅ Máxima calidad
- ✅ Soporte oficial
- ✅ Documentación completa

**Desventajas:**
- ❌ Requiere tarjeta de crédito
- ❌ Se cobra por uso
- ❌ Más lento que Groq

**Configuración:**
```env
OPENAI_API_KEY=sk-tu-api-key-aqui
OPENAI_BASE_URL=
WHISPER_MODEL=whisper-1
```

**Obtener API Key:**
1. Ve a https://platform.openai.com/api-keys
2. Inicia sesión o crea cuenta
3. Crea una nueva API Key
4. Agrega créditos en "Billing"

---

### 3. DeepSeek

**Ventajas:**
- ✅ Económico
- ✅ Buena calidad
- ✅ API compatible

**Configuración:**
```env
OPENAI_API_KEY=tu-api-key-aqui
OPENAI_BASE_URL=https://api.deepseek.com/v1
WHISPER_MODEL=deepseek-whisper
```

**Obtener API Key:**
1. Ve a https://platform.deepseek.com/
2. Regístrate
3. Crea API Key

---

### 4. Ollama (Local)

**Ventajas:**
- ✅ Totalmente gratis
- ✅ Sin límites
- ✅ Privacidad total
- ✅ Funciona offline

**Desventajas:**
- ❌ Requiere hardware potente
- ❌ Más lento
- ❌ Calidad variable

**Configuración:**
```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
WHISPER_MODEL=whisper:large
```

**Instalar:**
```bash
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Descargar modelo Whisper
ollama pull whisper:large

# Iniciar servidor
ollama serve
```

---

## 📊 Comparativa

| Proveedor | Precio | Velocidad | Calidad | Requiere CC |
|-----------|--------|-----------|---------|-------------|
| **Groq** | Gratis* | ⚡⚡⚡ | ⭐⭐⭐⭐ | No |
| **OpenAI** | $0.006/min | ⚡⚡ | ⭐⭐⭐⭐⭐ | Sí |
| **DeepSeek** | $ | ⚡⚡ | ⭐⭐⭐⭐ | Sí |
| **Ollama** | Gratis | ⚡ | ⭐⭐⭐ | No |

*Groq tiene límites gratis generosos, luego es de pago

---

## 🔧 Cambiar de Proveedor

1. Edita `.env`:
```bash
nano .env
```

2. Actualiza las variables:
```env
OPENAI_API_KEY=nueva-key
OPENAI_BASE_URL=nueva-url
WHISPER_MODEL=nuevo-modelo
```

3. Reinicia los contenedores:
```bash
docker compose restart
```

¡Listo! El mismo código funciona con cualquier proveedor.

---

## 🎯 Recomendación

**Para empezar:** Usa **Groq** - es gratis, rápido y no requiere tarjeta de crédito.

**Para producción:** Evalúa según tu presupuesto y necesidades:
- Bajo costo: Groq o DeepSeek
- Máxima calidad: OpenAI
- Privacidad total: Ollama local

---

## 📝 Ejemplos de Configuración

### .env para Groq
```env
OPENAI_API_KEY=gsk_ABC123xyz
OPENAI_BASE_URL=https://api.groq.com/openai/v1
WHISPER_MODEL=whisper-large-v3
```

### .env para OpenAI
```env
OPENAI_API_KEY=sk-proj-ABC123xyz
OPENAI_BASE_URL=
WHISPER_MODEL=whisper-1
```

### .env para Ollama Local
```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
WHISPER_MODEL=whisper:large
```

---

## 🆘 Troubleshooting

### Error 401 Unauthorized
- Verifica que la API Key sea correcta
- Revisa que no tenga espacios al inicio/final

### Error 404 Not Found
- Verifica que `OPENAI_BASE_URL` sea correcta
- Asegúrate de que el modelo exista en ese proveedor

### Error de Timeout
- El modelo puede estar muy ocupado
- Intenta con un modelo más rápido (ej: `whisper-large-v3-turbo`)
- Aumenta el timeout en `app/celery_app.py`

### La transcripción es incorrecta
- Prueba con otro modelo
- Verifica que el audio del video sea claro
- Ajusta `SCENE_DETECT_THRESHOLD` si hay mucho ruido

---

## 🔗 Enlaces Útiles

- [Groq Console](https://console.groq.com/)
- [OpenAI Platform](https://platform.openai.com/)
- [DeepSeek Platform](https://platform.deepseek.com/)
- [Ollama](https://ollama.com/)
- [OpenAI SDK Docs](https://github.com/openai/openai-python)
