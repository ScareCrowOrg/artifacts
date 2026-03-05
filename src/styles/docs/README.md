---
processed: true
processed_date: 2025-12-11
generated_docs:
  - docs/official/frontend/design-system/theme-system.md
  - docs/official/frontend/design-system/components-utilities.md
themes:
  - design-system
  - css-variables
  - tokens
  - documentation
modules:
  - styles
code_verified: true
dead_docs_found: false
---

# Documentação de Estilos - ScareVerse Design System

## 📋 Índice

Este diretório contém documentação detalhada sobre o sistema de design e estilos utilizados no **cockpit-vue**.

### Documentos Disponíveis

1. **[../variables.css](../variables.css)** - CSS Variables (Design Tokens)
   - Paleta de cores (light/dark themes)
   - Espaçamentos e tipografia
   - Sombras, bordas e transições
   - Z-index e tamanhos de componentes

2. **[../base.css](../base.css)** - Estilos Base e Reset
   - CSS Reset customizado
   - Estilos globais (body, html)
   - Keyframe animations (@keyframes)

3. **[../buttons.css](../buttons.css)** - Sistema de Botões
   - Classes `.btn`, `.btn-primary`, `.btn-secondary`
   - Variantes de tamanho (sm, lg)
   - Estados (hover, active, disabled)

4. **[../forms.css](../forms.css)** - Formulários
   - Inputs, textareas, selects
   - Checkboxes e radios
   - Form groups e labels

5. **[../components.css](../components.css)** - Componentes UI
   - Cards (`.card`, `.card-header`, `.card-body`)
   - Alerts (`.alert-success`, `.alert-error`)
   - Modals (`.modal-overlay`, `.modal-content`)

6. **[../utilities.css](../utilities.css)** - Classes Utilitárias
   - Flexbox helpers (`.flex`, `.flex-col`)
   - Spacing helpers (`.mt-sm`, `.p-md`)
   - Text utilities (`.text-center`, `.text-error`)

---

## 🎨 Design System Overview

### Filosofia

O **ScareVerse Design System** foi desenvolvido com foco em:

1. **Consistência Visual**: Uso de CSS Variables para tokens de design centralizados
2. **Acessibilidade**: Suporte a temas (light/dark), reduced motion, high contrast
3. **Modularidade**: Arquivos CSS separados por responsabilidade
4. **Performance**: Classes utilitárias para evitar CSS duplicado

### Arquitetura de Importação

```css
/* src/styles/index.css */
@import './variables.css'; /* 1º - Define tokens */
@import './base.css'; /* 2º - Reset e global */
@import './buttons.css'; /* 3º - Componentes */
@import './forms.css';
@import './components.css';
@import './utilities.css'; /* Último - Override helpers */
```

**⚠️ IMPORTANTE**: A ordem de importação não deve ser alterada sem análise cuidadosa de impacto.

---

## 📖 Guia de Uso

### Como Usar Design Tokens (CSS Variables)

#### Exemplo 1: Cores

```vue
<template>
  <button class="custom-btn">Clique aqui</button>
</template>

<style scoped>
.custom-btn {
  background: var(--color-primary); /* #6200ea (roxo) */
  color: var(--color-text-on-primary); /* #ffffff (branco) */
  border-radius: var(--radius-md); /* 8px */
  padding: var(--space-sm) var(--space-md); /* 8px 16px */
}

.custom-btn:hover {
  background: var(--color-primary-hover); /* #7c4dff (roxo claro) */
}
</style>
```

#### Exemplo 2: Espaçamentos

```vue
<style scoped>
.card-container {
  margin-top: var(--space-lg); /* 24px */
  padding: var(--space-xl); /* 32px */
  gap: var(--space-md); /* 16px */
}
</style>
```

#### Exemplo 3: Tipografia

```vue
<style scoped>
.heading {
  font-size: var(--font-size-2xl); /* 24px */
  font-weight: var(--font-weight-bold); /* 700 */
  line-height: var(--line-height-tight); /* 1.25 */
}
</style>
```

---

## 🌗 Suporte a Dark Mode

### Como Funciona

O Design System usa o atributo `[data-theme='dark']` para aplicar o tema escuro:

```html
<!-- Light mode (padrão) -->
<html>
  <!-- Dark mode -->
  <html data-theme="dark"></html>
</html>
```

### Variáveis que Mudam no Dark Mode

```css
/* Light mode */
--color-background: #f5f5f7;
--color-surface: #ffffff;
--color-text-primary: #1d1d1f;

/* Dark mode */
[data-theme='dark'] {
  --color-background: #0a0a0f;
  --color-surface: #1a1a1f;
  --color-text-primary: #e5e7eb;
}
```

### Ativar Dark Mode (Vue)

```javascript
// Composable: useTheme.js
export function useTheme() {
  const setDarkMode = (enabled) => {
    if (enabled) {
      document.documentElement.setAttribute('data-theme', 'dark')
    } else {
      document.documentElement.removeAttribute('data-theme')
    }
  }

  return { setDarkMode }
}
```

---

## ♿ Acessibilidade

### Reduced Motion

Usuários com preferência por animações reduzidas recebem transições desabilitadas:

```css
@media (prefers-reduced-motion: reduce) {
  :root {
    --transition-fast: 0s;
    --transition-base: 0s;
    --transition-slow: 0s;
  }
}
```

### High Contrast

Aumenta contraste de bordas e sombras para melhor visibilidade:

```css
@media (prefers-contrast: high) {
  :root {
    --color-border: #a0a0a0;
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.3);
  }
}
```

---

## 🔍 Referências Rápidas

### Paleta de Cores

| Token               | Cor                | Uso                      |
| ------------------- | ------------------ | ------------------------ |
| `--color-primary`   | #6200ea (roxo)     | Botões principais, links |
| `--color-secondary` | #03dac6 (ciano)    | Ações secundárias        |
| `--color-success`   | #22c55e (verde)    | Feedbacks positivos      |
| `--color-error`     | #ef4444 (vermelho) | Erros e alertas          |
| `--color-warning`   | #f59e0b (laranja)  | Avisos                   |
| `--color-info`      | #3b82f6 (azul)     | Informações              |

### Escala de Espaçamentos

| Token         | Valor | Uso Típico           |
| ------------- | ----- | -------------------- |
| `--space-xs`  | 4px   | Gaps mínimos         |
| `--space-sm`  | 8px   | Padding pequeno      |
| `--space-md`  | 16px  | Padding padrão       |
| `--space-lg`  | 24px  | Margens entre seções |
| `--space-xl`  | 32px  | Espaçamentos grandes |
| `--space-2xl` | 48px  | Seções principais    |

### Tamanhos de Fonte

| Token              | Valor | Uso                |
| ------------------ | ----- | ------------------ |
| `--font-size-xs`   | 12px  | Captions, notas    |
| `--font-size-sm`   | 14px  | Body secundário    |
| `--font-size-base` | 16px  | Body principal     |
| `--font-size-lg`   | 18px  | Subtítulos         |
| `--font-size-2xl`  | 24px  | Títulos de seção   |
| `--font-size-3xl`  | 30px  | Títulos principais |

---

## 🚀 Migração para Tailwind (Planejada)

Este Design System está em processo de migração para **Tailwind CSS**.

**Status**: Planejamento  
**Documento**: [DESIGN_SYSTEM_SURVEY.md](../../docs/DESIGN_SYSTEM_SURVEY.md)  
**Prazo estimado**: 12 semanas (3 meses)

### Por Que Migrar?

1. **Produtividade**: Classes utilitárias aceleram desenvolvimento
2. **Bundle menor**: Purge automático de CSS não utilizado (~80% redução)
3. **Consistência**: Menos CSS customizado para manter
4. **Comunidade**: Ecossistema robusto e plugins especializados

### Tokens Serão Mantidos

Todos os design tokens (cores, espaçamentos, tipografia) serão mapeados para a configuração Tailwind, preservando a identidade visual do ScareVerse.

---

## 📚 Recursos Adicionais

### Documentação Relacionada

- [README Principal](../../README.md)
- [Componentes](../../components/README.md)
- [DESIGN_SYSTEM_SURVEY.md](../../docs/DESIGN_SYSTEM_SURVEY.md) - Levantamento de migração Tailwind
- [RULESET.md](../../../RULESET.md) - Governança do projeto

### Ferramentas Úteis

- **Figma**: Design System completo (link interno)
- **Storybook**: Biblioteca de componentes (planejado)
- **Chromatic**: Visual regression testing (planejado)

---

## 🤝 Contribuindo

### Ao Adicionar Novos Tokens

1. **Edite `variables.css`**:

   ```css
   :root {
     --seu-novo-token: valor;
   }
   ```

2. **Documente aqui** (este README):
   - Adicione à tabela de referência rápida
   - Explique o uso pretendido

3. **Teste em Dark Mode**:
   - Defina valor alternativo em `[data-theme='dark']`

4. **Valide Acessibilidade**:
   - Teste contraste de cores (WCAG AA: 4.5:1)
   - Valide com axe-core ou Lighthouse

### Ao Criar Novos Componentes CSS

1. **Prefira reutilizar tokens existentes**
2. **Documente classes novas** em comentários
3. **Teste responsividade** (mobile, tablet, desktop)
4. **Valide acessibilidade** (keyboard navigation, screen readers)

---

## 📝 Changelog

### v1.0.0 (Novembro 2025)

- Criação do Design System com CSS Variables
- Suporte a light/dark themes
- Acessibilidade (reduced motion, high contrast)
- Documentação completa

---

**Última Atualização**: Novembro 2025  
**Autor**: Frontend Agent  
**Status**: Ativo
