# Store frontend

How the Arcana Crochet interface is organized: navigation, pages, components and visual identity. The customer-facing text is in Brazilian Portuguese; page and URL names below are the real ones.

## Visual identity

| Token | Color | Use |
| --- | --- | --- |
| `creme` | `#fbf9e4` | background of every page |
| `azul` | `#17597c` | main buttons, logo, discount badge |
| `petroleo` | `#034947` | text, top bar, footer |
| `verde` | `#015d5c` | "Ofertas do dia" block, Pix price |
| `turquesa` | `#2e7f83` | stars, focus, details |
| `ardosia` | `#195261` | secondary text |

- **Typography:** Fraunces (headings, same family as the brand's posts) and Montserrat (body). Both are self-hosted in `static/fonts/` because the CSP only allows fonts from the site itself.
- **Signatures:**
  - **Shell stitch:** scalloped edge on the colored blocks and the footer (`.concha-baixo`, `.concha-cima`).
  - **Portal:** every product photo sits in an arch (`.arco`), which opens a little on hover.
  - **Logo wave:** the stroke under "crochet" becomes a section divider (`#i-onda`).
  - **Discount badge:** a four-pointed star, like the sparkles in the logo (`.selo-desconto`).
- **Motion:** only the hero photo entrance and the twinkling stars. Respects `prefers-reduced-motion`.

## Navigation map

```
Home (/)
├── Shop: all pieces (/loja/)        ── filters, sorting, pagination
│   ├── Category (/c/<slug>/)        ── with subcategories
│   └── Search (/busca/?q=)          ── ignores accents, suggests similar pieces when nothing matches
├── Product (/p/<slug>/)             ── quick shipping quote (HTMX)
├── Bag (/sacola/)                   ── quantity, coupon and shipping without reloading (HTMX)
├── Checkout
│   ├── 1. Sign in (/checkout/identificacao/)  ── only for visitors who aren't logged in
│   ├── 2. Delivery (/checkout/entrega/)
│   ├── 3. Payment (/checkout/pagamento/)
│   └── 4. Review (/checkout/revisao/)  ── creates the order
├── My account (/minha-conta/)       ── orders
│   ├── Order (/minha-conta/pedidos/<code>/)  ── timeline and tracking
│   ├── Addresses (/minha-conta/enderecos/)
│   └── Review a piece (/minha-conta/avaliar/<item>/)  ── only after delivery
└── Account (allauth): log in, sign up, email code, password, 2FA (/conta/...)
```

## Pages

### 1. Home (`catalogo/home.html`)
1. **Perks bar:** Pix discount, interest-free installments, free shipping (values come from `settings.LOJA`).
2. **Sticky header:** logo, **prominent search** in the middle (full width on phones), account and bag with a counter.
3. **Category menu:** categories with subcategories open a panel; on phones, a side drawer.
4. **Hero:** blue block with a shell-stitch edge, photo of the baskets in a portal.
5. **Promotional banners:** weekly deals, made to order, free shipping.
6. **Categories** in arches.
7. **Carousels:** "Escolhidas pela Kamilly" (featured), "Ofertas do dia" (green block), new arrivals and best sellers.
8. **Who's behind it** (Kamilly) and **Why Arcana**.
9. **Footer:** links, customer service, payment methods and badges (secure site, payments by Asaas, 7 days to return).

### 2. Category, search and listing (`catalogo/listagem.html`)
- **Side filters** ("Filtrar" drawer on phones): price range (shortcuts + min/max), color (with swatch), size, material, availability (ready to ship / made to order) and "on sale only". Each option shows how many pieces it has.
- Since it's a single-brand store, **"brand" becomes "material"** and the specs become color/size.
- **Sorting:** relevance, best sellers, lowest/highest price, newest, best rated.
- Filters and sorting swap only the grid (HTMX) and update the URL; without JavaScript the form submits normally.
- **Search** matches name, description, material, category and colors without accents (the `Produto.busca` column); with no results it suggests pieces with a similar name (typos like "urço").
- **Card:** photo in an arch, discount badge, "Sob encomenda"/"Esgotado" tag, rating, was/now price, Pix price and installments.

### 3. Product page (`catalogo/produto.html`)
- **Gallery** with thumbnails, swipe on phones and an optional video (`Produto.video`).
- **Variation picker:** color swatches and size buttons; combinations without stock are struck through. Without JavaScript it becomes a `<select>`.
- **Buy box:** Pix price highlighted, card price with installments, installment list, stock notice ("Peça única", "Últimas 2") or production time, quantity, "Adicionar à sacola" and "Comprar agora".
- **Quick shipping quote** by CEP (PAC and SEDEX with delivery time).
- **Spec sheet** (`ProdutoEspecificacao` + product data) and care instructions.
- **Reviews:** average, distribution by stars, "Compra verificada" and the store's reply.

### 4. Bag and checkout (`pedidos/sacola.html`, `pedidos/checkout/*`)
- **Bag:** progress bar to free shipping, quantity with +/−, remove, coupon, CEP with PAC/SEDEX choice, total for Pix and card.
- **4-step checkout** with a slim header (no menu, to avoid distractions) and the order summary always visible:
  1. **Sign in:** log in with a password, **log in with an email code** (no password) or sign up. All of them return straight to delivery.
  2. **Delivery:** saved addresses as cards or a new address **filled in from the CEP (ViaCEP)**; shipping is recalculated when the address changes.
  3. **Payment:** Pix (with the savings highlighted) or card with installments. Card details will be typed in Asaas's environment.
  4. **Review:** everything confirmed with links to change it, a note to Kamilly and acceptance of the returns policy.

### 5. Order tracking (`pedidos/conta/pedido.html`)
- **Timeline:** Payment approved → Being prepared → Shipped → Delivered, with the date and time of each step.
- A box with what happens now: Pix QR code and "copia e cola" with the payment deadline (Pix goes straight to the store's account and is approved in the admin, see [deploy.md](deploy.md#receiving-pix-payments)), production notice, **tracking code with a copy button** and tracking link, or an invitation to review.
- Items, amounts, payment method and shipping address.

## Business rules in the interface

| Rule | Where it lives |
| --- | --- |
| Pix discount, interest-free installments, minimum installment, free shipping | `settings.LOJA` and `apps/core/precos.py` (the product page JS repeats the same math) |
| Shipping estimated by the CEP's region | `apps/pedidos/frete.py` (swapped for Melhor Envio without changing the pages) |
| Stock reservation when the order is created | `apps/pedidos/servicos.py` |
| Reviews only after delivery, with moderation | `apps/pedidos/views.avaliar` and the reviews admin |

## Development

```bash
npm install            # once (Node 20+)
npm run watch:css      # rebuilds the CSS while you edit templates
npm run build:css      # writes the minified static/css/app.css (committed to git)
python manage.py popular_demo   # demo pieces, orders and reviews
```

- The compiled CSS is committed so Docker doesn't need Node. **Run `npm run build:css` before committing** changes to templates, `frontend/app.css` or Python/JS files that carry CSS classes.
- No inline CSS or JS: the Content-Security-Policy blocks it. Dynamic colors (color swatches) use the SVG `fill` attribute.
- `static/js/loja.js` is progressive enhancement only: every page works without JavaScript.
- Test customer created by `popular_demo`: `cliente@arcana.test` / `arcana-demo-123`. With `DEBUG`, the order page has a "Simular pagamento aprovado" button.
