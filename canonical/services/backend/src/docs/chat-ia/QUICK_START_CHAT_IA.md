---
processed: true
processed_date: 2025-12-09
themes:
  - ai
  - chat
  - quickstart
  - getting-started
modules:
  - backend
  - frontend
code_verified: true
dead_docs_found: false
---
# Quick Start - Chat IA no Cockpit

Guia rápido para testar a integração do Chat IA.

## 🚀 Início Rápido (3 minutos)

### Passo 1: Iniciar o Backend
```bash
cd backend
pip3 install -r requirements.txt
python3 -m app.main
```

✅ Backend rodando em: `http://localhost:5051`

### Passo 2: Inicializar Dados
Em outro terminal:
```bash
# Criar tipos de célula
curl -X POST http://localhost:5051/api/seed-data

# Criar usuário teste
curl -X POST http://localhost:5051/api/usuarios/registrar \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Teste User",
    "email": "teste@scareverse.com"
  }'
```

📝 **Importante**: Copie o `id` retornado do usuário!

### Passo 3: Iniciar o Frontend
```bash
cd cockpit-vue
npm install
npm run dev
```

✅ Frontend rodando em: `http://localhost:5173`

### Passo 4: Usar o Chat
1. Abra `http://localhost:5173` no navegador
2. Veja o chat no topo da página
3. Digite: "Criar um sistema de login"
4. ✨ A IA criará uma célula automaticamente!

## 📋 Exemplos de Intenções

### Memória
```
"Memorizar os requisitos do projeto"
"Salvar informações sobre o usuário"
```

### Execução
```
"Executar um script Python"
"Rodar código de análise de dados"
```

### Edição
```
"Editar o componente de login"
"Modificar a estrutura do banco"
```

### Decomposição
```
"Dividir o projeto em etapas"
"Separar tarefas do sprint"
```

### Visualização
```
"Mostrar gráfico de vendas"
"Exibir dashboard de métricas"
```

## 🔧 Troubleshooting

### Backend não inicia
```bash
# Verificar porta em uso
lsof -i :5051

# Matar processo
kill -9 <PID>
```

### Frontend não conecta
- Verificar se backend está rodando: `curl http://localhost:5051/api/status`
- Verificar proxy no `vite.config.js`

### Chat não responde
- Abrir DevTools (F12) e verificar erros no console
- Verificar se o usuário foi criado
- Verificar chamada à API na aba Network

## 📚 Documentação Completa

- [CHAT_IA_INTEGRATION.md](./CHAT_IA_INTEGRATION.md) - Documentação completa
- [PORTS_CONFIGURATION.md](./PORTS_CONFIGURATION.md) - Configuração de portas
- [Current Implementation_PROXIMOS_PASSOS.md](../REFACTORING_SUMMARY.md) - Roadmap

## 🎯 Próximos Passos

Após testar, veja as próximas etapas em:
- [ETAPA_2_ROADMAP.md](./ETAPA_2_ROADMAP.md) - Integração com IA real

---

**Status**: Etapa 1 Completa ✅  
**Versão**: Current Implementation com Chat básico
