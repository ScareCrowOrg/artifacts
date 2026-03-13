#!/bin/bash
# Script de teste do fluxo completo do Sistema
# Documenta e valida todos os endpoints implementados

set -e

API_BASE="http://localhost:8000/api"

echo "=========================================="
echo "Teste do Fluxo Completo Sistema"
echo "=========================================="
echo ""

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Verificar status inicial
echo -e "${BLUE}1. Verificando status inicial...${NC}"
curl -s "$API_BASE/status" | python3 -m json.tool
echo ""

# 2. Inicializar seed data
echo -e "${BLUE}2. Inicializando dados de seed...${NC}"
curl -s -X POST "$API_BASE/seed-data" | python3 -m json.tool
echo ""

# 3. Registrar usuário
echo -e "${BLUE}3. Registrando usuário...${NC}"
USUARIO_RESPONSE=$(curl -s -X POST "$API_BASE/usuarios/registrar" \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Jogador Teste Sistema",
    "email": "mvp1@scareverse.com",
    "galaxia": "GalaxiaTeste"
  }')
echo "$USUARIO_RESPONSE" | python3 -m json.tool
USUARIO_ID=$(echo "$USUARIO_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo -e "${GREEN}Usuario ID: $USUARIO_ID${NC}"
echo ""

# 4. Obter primeiro tipo de célula
echo -e "${BLUE}4. Buscando tipo de célula...${NC}"
TIPO_CELULA_FILE=$(ls ../ScareFeraLab/Artefatos/canonicos/tipos_celula/ 2>/dev/null | head -1)
if [ -z "$TIPO_CELULA_FILE" ]; then
  echo "Tipo de célula não encontrado. Execute o seed-data primeiro."
  exit 1
fi
TIPO_CELULA_ID="${TIPO_CELULA_FILE%.json}"
echo -e "${GREEN}Tipo Celula ID: $TIPO_CELULA_ID${NC}"
echo ""

# 5. Criar célula
echo -e "${BLUE}5. Criando célula...${NC}"
CELULA_RESPONSE=$(curl -s -X POST "$API_BASE/celulas/criar" \
  -H "Content-Type: application/json" \
  -d "{
    \"tipoCelulaId\": \"$TIPO_CELULA_ID\",
    \"assignee_id\": \"$USUARIO_ID\",
    \"dadosIniciais\": {\"descricao\": \"Célula de teste\"}
  }")
echo "$CELULA_RESPONSE" | python3 -m json.tool
CELULA_ID=$(echo "$CELULA_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo -e "${GREEN}Celula ID: $CELULA_ID${NC}"
echo ""

# 6. Criar livro
echo -e "${BLUE}6. Criando livro...${NC}"
LIVRO_RESPONSE=$(curl -s -X POST "$API_BASE/livros/criar" \
  -H "Content-Type: application/json" \
  -d '{
    "tipoLivro": "MESTRE",
    "intencao": "Teste completo do Sistema: criar sistema de autenticação"
  }')
echo "$LIVRO_RESPONSE" | python3 -m json.tool
LIVRO_ID=$(echo "$LIVRO_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo -e "${GREEN}Livro ID: $LIVRO_ID${NC}"
echo ""

# 7. Adicionar célula ao livro
echo -e "${BLUE}7. Adicionando célula ao livro...${NC}"
curl -s -X POST "$API_BASE/livros/$LIVRO_ID/adicionar_celula" \
  -H "Content-Type: application/json" \
  -d "{\"celulaId\": \"$CELULA_ID\"}" | python3 -m json.tool
echo ""

# 8. Executar célula
echo -e "${BLUE}8. Executando célula...${NC}"
curl -s -X POST "$API_BASE/celulas/$CELULA_ID/executar" \
  -H "Content-Type: application/json" \
  -d '{
    "parametros": {
      "operacao": "teste",
      "valor": 42
    }
  }' | python3 -m json.tool
echo ""

# 9. Obter célula atualizada
echo -e "${BLUE}9. Obtendo célula atualizada...${NC}"
curl -s "$API_BASE/celulas/$CELULA_ID" | python3 -m json.tool
echo ""

# 10. Atualizar célula
echo -e "${BLUE}10. Atualizando célula para finalizada...${NC}"
curl -s -X PUT "$API_BASE/celulas/$CELULA_ID/atualizar" \
  -H "Content-Type: application/json" \
  -d '{
    "estado": "finalizado",
    "fragmentos": [
      {
        "tipo": "execucao",
        "resultado": "Execução completa com sucesso"
      },
      {
        "tipo": "memoria",
        "conteudo": "Teste realizado: operação=teste, valor=42"
      }
    ]
  }' | python3 -m json.tool
echo ""

# 11. Obter livro completo
echo -e "${BLUE}11. Obtendo livro completo...${NC}"
curl -s "$API_BASE/livros/$LIVRO_ID" | python3 -m json.tool
echo ""

# 12. Listar células do usuário
echo -e "${BLUE}12. Listando células do usuário...${NC}"
curl -s "$API_BASE/usuarios/$USUARIO_ID/celulas" | python3 -m json.tool
echo ""

# 13. Status final
echo -e "${BLUE}13. Status final do sistema...${NC}"
curl -s "$API_BASE/status" | python3 -m json.tool
echo ""

echo "=========================================="
echo -e "${GREEN}Teste completo finalizado com sucesso!${NC}"
echo "=========================================="
echo ""
echo "IDs gerados neste teste:"
echo "  Usuario ID: $USUARIO_ID"
echo "  Celula ID:  $CELULA_ID"
echo "  Livro ID:   $LIVRO_ID"
echo ""
