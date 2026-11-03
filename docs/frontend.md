# Frontend da loja

Como a interface da Arcana Crochet está organizada: navegação, telas, componentes e identidade visual.

## Identidade visual

| Token | Cor | Uso |
| --- | --- | --- |
| `creme` | `#fbf9e4` | fundo de todas as páginas |
| `azul` | `#17597c` | botões principais, logo, selo de desconto |
| `petroleo` | `#034947` | texto, faixa do topo, rodapé |
| `verde` | `#015d5c` | bloco "Ofertas do dia", preço no Pix |
| `turquesa` | `#2e7f83` | estrelas, foco, detalhes |
| `ardosia` | `#195261` | texto secundário |

- **Tipografia:** Fraunces (títulos, mesma família dos posts da marca) e Montserrat (texto). Ambas auto-hospedadas em `static/fonts/` porque a CSP só aceita fontes do próprio site.
- **Assinaturas:**
  - **Ponto concha:** borda recortada em arcos nos blocos coloridos e no rodapé (`.concha-baixo`, `.concha-cima`).
  - **Portal:** toda foto de produto fica num arco (`.arco`), que se abre um pouco no hover.
  - **Onda do logo:** o traço sob "crochet" vira divisor de seção (`#i-onda`).
  - **Selo de desconto:** estrela de quatro pontas, como os brilhos do logo (`.selo-desconto`).
- **Movimento:** só a entrada da foto do hero e o brilho das estrelinhas. Respeita `prefers-reduced-motion`.

## Mapa de navegação

```
Início (/)
├── Loja: todas as peças (/loja/)  ── filtros, ordenação, paginação
│   ├── Categoria (/c/<slug>/)     ── com subcategorias
│   └── Busca (/busca/?q=)         ── ignora acentos, sugere parecidos se não achar nada
├── Produto (/p/<slug>/)           ── frete rápido (HTMX)
├── Sacola (/sacola/)              ── quantidade, cupom e frete sem recarregar (HTMX)
├── Checkout
│   ├── 1. Identificação (/checkout/identificacao/)  ── só para quem não está logado
│   ├── 2. Entrega (/checkout/entrega/)
│   ├── 3. Pagamento (/checkout/pagamento/)
│   └── 4. Revisão (/checkout/revisao/)  ── cria o pedido
├── Minha conta (/minha-conta/)    ── pedidos
│   ├── Pedido (/minha-conta/pedidos/<código>/)  ── linha do tempo e rastreio
│   ├── Endereços (/minha-conta/enderecos/)
│   └── Avaliar peça (/minha-conta/avaliar/<item>/)  ── só após a entrega
└── Conta (allauth): entrar, criar conta, código por e-mail, senha, 2FA (/conta/...)
```

## Telas

### 1. Página inicial (`catalogo/home.html`)
1. **Faixa de vantagens:** desconto no Pix, parcelas sem juros, frete grátis (valores vêm de `settings.LOJA`).
2. **Cabeçalho fixo:** logo, **busca em destaque** no centro (ocupa a linha inteira no celular), conta e sacola com contador.
3. **Menu de categorias:** categorias com subcategorias abrem um painel; no celular, gaveta lateral.
4. **Hero:** bloco azul com borda de concha, foto das cestas num portal.
5. **Banners promocionais:** Ofertas da semana, Sob encomenda, Frete grátis.
6. **Categorias** em arcos.
7. **Carrosséis:** "Escolhidas pela Kamilly" (destaques), "Ofertas do dia" (bloco verde), novidades e mais vendidas.
8. **Quem está por trás** (Kamilly) e **Por que Arcana**.
9. **Rodapé:** links, atendimento, formas de pagamento e selos (site seguro, pagamento pelo Asaas, 7 dias para trocar).

### 2. Categoria, busca e listagem (`catalogo/listagem.html`)
- **Filtros laterais** (gaveta "Filtrar" no celular): faixa de preço (atalhos + mínimo/máximo), cor (com amostra), tamanho, material, disponibilidade (pronta entrega / sob encomenda) e "só promoção". Cada opção mostra quantas peças tem.
- Por ser uma loja de uma marca só, **"marca" vira "material"** e as especificações viram cor/tamanho.
- **Ordenação:** relevância, mais vendidos, menor/maior preço, novidades, mais bem avaliados.
- Filtros e ordenação trocam só a grade (HTMX) e atualizam a URL; sem JavaScript, o formulário envia normalmente.
- **Card:** foto em arco, selo de desconto, etiqueta "Sob encomenda"/"Esgotado", nota, preço "de/por", preço no Pix e parcelamento.

### 3. Página do produto (`catalogo/produto.html`)
- **Galeria** com miniaturas, deslizar no celular e vídeo opcional (`Produto.video`).
- **Seletor de variação:** amostras de cor e botões de tamanho; combinações sem estoque ficam riscadas. Sem JavaScript, vira um `<select>`.
- **Caixa de compra:** preço no Pix em destaque, preço no cartão com parcelas, lista de parcelas, aviso de estoque ("Peça única", "Últimas 2") ou prazo de produção, quantidade, "Adicionar à sacola" e "Comprar agora".
- **Frete rápido** por CEP (PAC e SEDEX com prazo).
- **Ficha técnica** (`ProdutoEspecificacao` + dados do produto), cuidados com a peça.
- **Avaliações:** média, distribuição por estrelas, "Compra verificada" e resposta da loja.

### 4. Sacola e checkout (`pedidos/sacola.html`, `pedidos/checkout/*`)
- **Sacola:** barra de progresso até o frete grátis, quantidade com +/−, remover, cupom, CEP com escolha de PAC/SEDEX, total no Pix e no cartão.
- **Checkout em 4 etapas** com cabeçalho enxuto (sem menu, para não distrair) e resumo do pedido sempre visível:
  1. **Identificação:** entrar com senha, **entrar com código por e-mail** (sem senha) ou criar conta. Voltam direto para a entrega.
  2. **Entrega:** endereços salvos em cartões ou novo endereço com **preenchimento automático pelo CEP (ViaCEP)**; o frete recalcula ao trocar de endereço.
  3. **Pagamento:** Pix (com a economia em destaque) ou cartão com parcelas. Os dados do cartão serão digitados no ambiente do Asaas.
  4. **Revisão:** confirmação de tudo com links para alterar, recado para a Kamilly e aceite da política de trocas.

### 5. Acompanhamento do pedido (`pedidos/conta/pedido.html`)
- **Linha do tempo:** Pagamento aprovado → Em separação → Enviado → Entregue, com data e hora de cada etapa.
- Caixa com o que acontece agora: instruções de Pix, aviso de produção, **código de rastreio com botão copiar** e link de rastreamento, ou convite para avaliar.
- Itens, valores, forma de pagamento e endereço de entrega.

## Regras de negócio na interface

| Regra | Onde fica |
| --- | --- |
| Desconto no Pix, parcelas sem juros, parcela mínima, frete grátis | `settings.LOJA` e `apps/core/precos.py` (o JS da página do produto repete a mesma conta) |
| Frete estimado por região do CEP | `apps/pedidos/frete.py` (troca pelo Melhor Envio sem mudar as telas) |
| Reserva de estoque ao criar o pedido | `apps/pedidos/servicos.py` |
| Avaliação só depois da entrega, com moderação | `apps/pedidos/views.avaliar` e painel de avaliações |

## Desenvolvimento

```bash
npm install            # uma vez (Node 20+)
npm run watch:css      # recompila o CSS enquanto você edita templates
npm run build:css      # gera static/css/app.css minificado (versionado no git)
python manage.py popular_demo   # peças, pedidos e avaliações de exemplo
```

- O CSS compilado é versionado para o Docker não precisar de Node. **Rode `npm run build:css` antes de commitar** mudanças em templates ou em `frontend/app.css`.
- Sem CSS ou JS inline: a Content-Security-Policy bloqueia. Cores dinâmicas (amostras de cor) usam o atributo `fill` de SVG.
- `static/js/loja.js` é só melhoria progressiva: todas as telas funcionam sem JavaScript.
- Cliente de teste criada pelo `popular_demo`: `cliente@arcana.test` / `arcana-demo-123`. Em `DEBUG`, o pedido tem o botão "Simular pagamento aprovado".
