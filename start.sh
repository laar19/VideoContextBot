#!/bin/bash
# Script de inicio rápido para VideoContextBot

set -e

echo "🚀 VideoContextBot - Setup Inicial"
echo "=================================="
echo ""

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose no está instalado"
    exit 1
fi

echo "✅ Docker y Docker Compose verificados"
echo ""

# Crear directorios necesarios
echo "📁 Creando directorios..."
mkdir -p output temp logs db
echo "✅ Directorios creados"
echo ""

# Verificar .env
if [ ! -f .env ]; then
    echo "⚠️  .env no existe. Copiando desde .env.example..."
    cp .env.example .env
    echo "❗ IMPORTANTE: Edita .env y configura:"
    echo "   - OPENAI_API_KEY"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - ALLOWED_USER_IDS (tu user ID de Telegram)"
    echo ""
    read -p "Presiona Enter después de configurar .env..."
fi

# Verificar variables críticas
if grep -q "sk-tu-api-key-aqui" .env; then
    echo "❗ ERROR: Debes configurar OPENAI_API_KEY en .env"
    exit 1
fi

echo "✅ Configuración verificada"
echo ""

# Construir y levantar
echo "🔨 Construyendo contenedores..."
docker-compose up --build -d

echo ""
echo "✅ ¡VideoContextBot está corriendo!"
echo ""
echo "📱 Interfaces disponibles:"
echo "   - API:       http://localhost:8000"
echo "   - Docs API:  http://localhost:8000/docs"
echo "   - Web:       http://localhost:7860"
echo ""
echo "📊 Ver logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Detener:"
echo "   docker-compose down"
echo ""
