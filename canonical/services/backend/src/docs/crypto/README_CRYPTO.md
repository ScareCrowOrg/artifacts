---
processed: true
processed_date: 2025-12-08
themes:
  - security
  - encryption
  - cryptography
  - backend
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Crypto Utils - Secure Data Encryption

## Visão Geral

O módulo `crypto_utils.py` fornece funções para criptografar/descriptografar dados sensíveis no ScareVerse, como API keys de modelos de IA.

## Implementação

Utiliza **Fernet** (symmetric encryption) da biblioteca `cryptography`:
- Algoritmo: AES-128 em modo CBC
- Autenticação: HMAC para integridade
- Formato: Base64 encoding

## Configuração

### 1. Gerar Chave de Criptografia

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Adicionar ao `.env`

```env
ENCRYPTION_KEY=sua-chave-gerada-aqui
```

**⚠️ IMPORTANTE:**
- Nunca commite a chave no repositório
- Use uma chave diferente para cada ambiente (dev, staging, prod)
- Guarde a chave em local seguro (ex: AWS Secrets Manager, 1Password)

## Uso

### Criptografar Valor

```python
from app.crypto_utils import encrypt_value

api_key = "my-secret-key-12345"
encrypted = encrypt_value(api_key)
# Resultado: "gAAAAABhN..."
```

### Descriptografar Valor

```python
from app.crypto_utils import decrypt_value

encrypted = "gAAAAABhN..."
decrypted = decrypt_value(encrypted)
# Resultado: "my-secret-key-12345"
```

### Verificar Configuração

```python
from app.crypto_utils import is_encryption_configured

if is_encryption_configured():
    print("Encryption is ready!")
else:
    print("ENCRYPTION_KEY not configured")
```

## Integração com Database

O módulo `database.py` integra automaticamente a criptografia:

### Ao Salvar (Insert/Update)

```python
# apiKey é criptografada automaticamente
modelo = ModeloIA(
    nome="Gemini Pro",
    provider="gemini",
    modeloId="gemini-pro",
    apiKey="my-secret-key"
)

db.insert("modelos_ia", modelo, is_canonical=True)
# JSON salvo com apiKey criptografada
```

### Ao Ler (Find)

```python
# apiKey é descriptografada automaticamente
modelo = db.find_one("modelos_ia", modelo_id, ModeloIA, is_canonical=True)
print(modelo.apiKey)  # "my-secret-key" (descriptografado)
```

## Campos Criptografados

Atualmente, apenas o campo `apiKey` dos modelos IA é criptografado.

Para adicionar novos campos:
1. Edite `_encrypt_sensitive_fields()` em `database.py`
2. Adicione lógica para o novo campo
3. Atualize `_decrypt_sensitive_fields()` correspondentemente

## Segurança

### Boas Práticas

✅ **Fazer:**
- Usar chave forte gerada pela biblioteca
- Rotacionar chaves periodicamente
- Guardar chaves em secret management
- Usar diferentes chaves por ambiente

❌ **Não Fazer:**
- Commitar chaves no código
- Usar chaves fracas ou previsíveis
- Compartilhar chaves entre ambientes
- Expor chaves em logs ou dumps

### Troubleshooting

#### "ENCRYPTION_KEY not configured"
- Adicione `ENCRYPTION_KEY=...` ao `.env`
- Gere nova chave com o comando acima

#### "Failed to decrypt value"
- Chave de descriptografia diferente da usada para criptografar
- Dados corrompidos
- Chave inválida no `.env`

#### Rotação de Chaves

Para rotacionar chaves:
1. Gere nova chave
2. Descriptografe todos os valores com chave antiga
3. Atualize `ENCRYPTION_KEY` no `.env`
4. Re-criptografe todos os valores com nova chave

## Testes

Execute os testes de criptografia:

```bash
pytest tests/test_crypto_utils.py -v
pytest tests/test_modelos_ia_encryption.py -v
```

## Referências

- [cryptography.io - Fernet](https://cryptography.io/en/latest/fernet/)
- [OWASP Cryptographic Storage](https://owasp.org/www-project-cheat-sheets/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

---

**Última Atualização**: Novembro 2024  
**Versão**: 1.0 (Implementação inicial)
