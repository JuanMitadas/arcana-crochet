/*
  Arcana Crochet — store behaviors.
  Everything here is progressive enhancement: without JavaScript the pages still work
  (forms submit normally, the variation picker becomes a <select>).
  No inline JS/CSS because of the Content-Security-Policy.
*/
(() => {
  "use strict";

  document.documentElement.classList.add("js");

  const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
  const $$ = (seletor, raiz = document) => Array.from(raiz.querySelectorAll(seletor));
  const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const brl = (centavos) => reais.format(centavos / 100);
  const lerJSON = (id) => {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  };

  /* --- Carousels ------------------------------------------------------- */
  function iniciarCarrosseis(raiz = document) {
    $$("[data-carrossel]", raiz).forEach((carrossel) => {
      if (carrossel.dataset.pronto) return;
      carrossel.dataset.pronto = "1";
      const trilho = $("[data-trilho]", carrossel);
      const anterior = $("[data-anterior]", carrossel);
      const proximo = $("[data-proximo]", carrossel);
      if (!trilho || !anterior || !proximo) return;

      const atualizar = () => {
        const fim = trilho.scrollWidth - trilho.clientWidth - 2;
        anterior.disabled = trilho.scrollLeft <= 2;
        proximo.disabled = trilho.scrollLeft >= fim;
        const semRolagem = trilho.scrollWidth <= trilho.clientWidth + 2;
        anterior.parentElement.hidden = semRolagem;
      };
      const rolar = (direcao) =>
        trilho.scrollBy({ left: direcao * trilho.clientWidth * 0.9, behavior: "smooth" });

      anterior.addEventListener("click", () => rolar(-1));
      proximo.addEventListener("click", () => rolar(1));
      trilho.addEventListener("scroll", atualizar, { passive: true });
      window.addEventListener("resize", atualizar);
      atualizar();
    });
  }

  /* --- Product gallery ------------------------------------------------- */
  function iniciarGaleria() {
    const galeria = $("[data-galeria]");
    if (!galeria) return;
    const slides = $$("[data-slide]", galeria);
    const miniaturas = $$("[data-miniatura]", galeria);

    const mostrar = (indice) => {
      slides.forEach((slide, i) => {
        slide.classList.toggle("ativo", i === indice);
        if (i !== indice && slide.tagName === "VIDEO") slide.pause();
      });
      miniaturas.forEach((botao) =>
        botao.setAttribute("aria-current", String(Number(botao.dataset.miniatura) === indice))
      );
    };
    miniaturas.forEach((botao) =>
      botao.addEventListener("click", () => mostrar(Number(botao.dataset.miniatura)))
    );

    // Swipe on the main photo
    let inicioX = null;
    const principal = $(".galeria__principal", galeria);
    principal?.addEventListener("touchstart", (e) => (inicioX = e.touches[0].clientX), { passive: true });
    principal?.addEventListener("touchend", (e) => {
      if (inicioX === null || slides.length < 2) return;
      const delta = e.changedTouches[0].clientX - inicioX;
      inicioX = null;
      if (Math.abs(delta) < 40) return;
      const atual = slides.findIndex((s) => s.classList.contains("ativo"));
      mostrar((atual + (delta < 0 ? 1 : -1) + slides.length) % slides.length);
    });
  }

  /* --- Prices (same rules as apps/core/precos.py) --------------------- */
  function calcularPrecos(centavos, regras) {
    const pix = Math.round((centavos * (100 - regras.pix)) / 100);
    let vezes = 1;
    for (let n = regras.parcelas; n >= 1; n--) {
      if (centavos / n >= regras.minima) {
        vezes = n;
        break;
      }
    }
    const opcoes = [];
    for (let n = 1; n <= vezes; n++) opcoes.push([n, Math.ceil(centavos / n)]);
    return { pix, vezes, parcela: Math.ceil(centavos / vezes), opcoes };
  }

  /* --- Variation picker (color and size) ------------------------------- */
  function iniciarSeletorVariacao() {
    const form = $("[data-compra]");
    const variacoes = lerJSON("dados-variacoes");
    const regras = lerJSON("regras-preco");
    if (!form || !variacoes || !regras) return;

    const select = $("[data-select-variacao]", form);
    const amostras = $("[data-seletor-amostras]", form);
    const simples = $("[data-seletor-simples]", form);
    const cores = $$("[data-cor]", form);
    const tamanhos = $$("[data-tamanho]", form);
    const quantidade = $("#quantidade", form);
    const botoes = $$("[data-botao-comprar]", form);
    const estoque = $("[data-estoque]", form);

    if (amostras && simples && (cores.length || tamanhos.length)) {
      amostras.hidden = false;
      simples.hidden = true;
    }

    const disponivel = (v) => regras.sobEncomenda || v.disponivel > 0;
    const escolhido = (lista) => lista.find((r) => r.checked)?.value ?? "";

    const atualizarPrecos = (centavos) => {
      const p = calcularPrecos(centavos, regras);
      const set = (sel, texto) => $$(sel, form).forEach((el) => (el.textContent = texto));
      set("[data-preco]", brl(centavos));
      set("[data-preco-pix]", brl(p.pix));
      set(
        "[data-parcelas]",
        p.vezes === 1 ? "à vista no cartão" : `${p.vezes}x de ${brl(p.parcela)} sem juros`
      );
      const lista = $("[data-lista-parcelas]", form);
      if (lista) {
        lista.replaceChildren(
          ...p.opcoes.map(([n, valor]) => {
            const li = document.createElement("li");
            li.textContent = `${n}x de ${brl(valor)} sem juros`;
            return li;
          })
        );
      }
    };

    const mensagemEstoque = (v) => {
      if (!estoque || regras.sobEncomenda) return;
      let texto;
      let icone = "#i-pacote";
      if (!v || v.disponivel <= 0) {
        texto = "Esta opção está esgotada no momento.";
        icone = "#i-fechar";
      } else if (v.disponivel === 1) {
        texto = "Peça única: só existe esta.";
        icone = "#i-brilho";
      } else if (v.disponivel <= 3) {
        texto = `Últimas ${v.disponivel} unidades, pronta para enviar.`;
      } else {
        texto = "Pronta para enviar.";
      }
      estoque.innerHTML = "";
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "icone text-turquesa");
      svg.setAttribute("aria-hidden", "true");
      const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", icone);
      svg.append(use);
      const span = document.createElement("span");
      span.textContent = texto;
      estoque.append(svg, span);
    };

    const aplicar = () => {
      const cor = escolhido(cores);
      const tamanho = escolhido(tamanhos);
      const nomeCor = $("[data-nome-cor]", form);
      if (nomeCor) nomeCor.textContent = cor;

      // Sizes with no stock for the chosen color are struck through
      tamanhos.forEach((radio) => {
        const existe = variacoes.some(
          (v) => (!cor || v.cor === cor) && v.tamanho === radio.value && disponivel(v)
        );
        radio.disabled = !existe;
      });
      if (tamanhos.length && $$("[data-tamanho]:checked:disabled", form).length) {
        const livre = tamanhos.find((r) => !r.disabled);
        if (livre) livre.checked = true;
      }

      const v = variacoes.find(
        (x) =>
          (!cores.length || x.cor === escolhido(cores)) &&
          (!tamanhos.length || x.tamanho === escolhido(tamanhos))
      );
      if (v && select) select.value = v.id;
      const pode = Boolean(v && disponivel(v));
      botoes.forEach((b) => (b.disabled = !pode));
      if (quantidade) {
        quantidade.max = regras.sobEncomenda ? 10 : Math.max(1, v?.disponivel ?? 1);
        if (Number(quantidade.value) > Number(quantidade.max)) quantidade.value = quantidade.max;
        quantidade.dispatchEvent(new Event("input"));
      }
      if (v) atualizarPrecos(v.preco);
      mensagemEstoque(v);
    };

    [...cores, ...tamanhos].forEach((r) => r.addEventListener("change", aplicar));
    if (cores.length || tamanhos.length) aplicar();
  }

  /* --- Quantity (+/-) -------------------------------------------------- */
  function iniciarQuantidades() {
    $$("[data-quantidade]").forEach((caixa) => {
      const input = $("input", caixa);
      const menos = $("[data-menos]", caixa);
      const mais = $("[data-mais]", caixa);
      const limitar = () => {
        const min = Number(input.min || 1);
        const max = Number(input.max || 99);
        let valor = Math.round(Number(input.value) || min);
        valor = Math.min(max, Math.max(min, valor));
        input.value = valor;
        menos.disabled = valor <= min;
        mais.disabled = valor >= max;
      };
      menos.addEventListener("click", () => {
        input.value = Number(input.value) - 1;
        limitar();
      });
      mais.addEventListener("click", () => {
        input.value = Number(input.value) + 1;
        limitar();
      });
      input.addEventListener("change", limitar);
      input.addEventListener("input", () => {
        menos.disabled = Number(input.value) <= Number(input.min || 1);
        mais.disabled = Number(input.value) >= Number(input.max || 99);
      });
      limitar();
    });
  }

  /* --- CEP: input mask and address autofill (ViaCEP) ------------------- */
  const mascararCep = (valor) => {
    const n = valor.replace(/\D/g, "").slice(0, 8);
    return n.length > 5 ? `${n.slice(0, 5)}-${n.slice(5)}` : n;
  };

  function iniciarCep(raiz = document) {
    $$("[data-cep-mascara], [data-cep]", raiz).forEach((input) => {
      if (input.dataset.cepPronto) return;
      input.dataset.cepPronto = "1";
      input.value = mascararCep(input.value);
      input.addEventListener("input", () => (input.value = mascararCep(input.value)));
    });

    $$("[data-endereco]", raiz).forEach((bloco) => {
      const cep = $("[data-cep]", bloco);
      const status = $("[data-cep-status]", bloco);
      if (!cep || bloco.dataset.viacep) return;
      bloco.dataset.viacep = "1";
      const campo = (nome) => $(`[name$="${nome}"]`, bloco);
      let ultimo = "";

      cep.addEventListener("input", async () => {
        const numeros = cep.value.replace(/\D/g, "");
        if (numeros.length !== 8 || numeros === ultimo) return;
        ultimo = numeros;
        if (status) status.textContent = "Buscando endereço…";
        try {
          const resposta = await fetch(`https://viacep.com.br/ws/${numeros}/json/`);
          const dados = await resposta.json();
          if (dados.erro) throw new Error("CEP não encontrado");
          const preencher = (nome, valor) => {
            const el = campo(nome);
            if (el && valor && !el.value) el.value = valor;
          };
          preencher("logradouro", dados.logradouro);
          preencher("bairro", dados.bairro);
          preencher("cidade", dados.localidade);
          const uf = campo("uf");
          if (uf && dados.uf) uf.value = dados.uf;
          if (status) status.textContent = "Endereço encontrado. Confira e complete o número.";
          campo("numero")?.focus();
        } catch {
          if (status) status.textContent = "Não achamos esse CEP. Preencha o endereço manualmente.";
        }
      });
    });
  }

  /* --- Copy (Pix code, tracking) -------------------------------------- */
  function iniciarCopiar() {
    $$("[data-copiar]").forEach((botao) => {
      botao.addEventListener("click", async () => {
        const alvo = $(botao.dataset.copiar);
        if (!alvo) return;
        try {
          await navigator.clipboard.writeText(alvo.value || alvo.textContent);
        } catch {
          alvo.select?.();
          document.execCommand?.("copy");
        }
        const original = botao.lastChild.textContent;
        botao.lastChild.textContent = "Copiado";
        setTimeout(() => (botao.lastChild.textContent = original), 2000);
      });
    });
  }

  /* --- Menus ----------------------------------------------------------- */
  function iniciarMenus() {
    const menu = $("[data-menu-mobile]");
    if (menu) {
      const fechar = () => menu.removeAttribute("open");
      $("[data-menu-fundo]", menu)?.addEventListener("click", fechar);
      $("[data-fechar-menu]", menu)?.addEventListener("click", fechar);
      menu.addEventListener("toggle", () =>
        document.body.classList.toggle("overflow-hidden", menu.open)
      );
    }
    const submenus = $$("[data-submenu]");
    submenus.forEach((d) =>
      d.addEventListener("toggle", () => {
        if (d.open) submenus.forEach((outro) => outro !== d && outro.removeAttribute("open"));
      })
    );
    document.addEventListener("click", (e) => {
      submenus.forEach((d) => !d.contains(e.target) && d.removeAttribute("open"));
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      submenus.forEach((d) => d.removeAttribute("open"));
      menu?.removeAttribute("open");
    });

    // Listing filters start collapsed on phones
    const filtros = $("[data-filtros]");
    if (filtros && window.matchMedia("(max-width: 1023px)").matches) {
      filtros.removeAttribute("open");
    }
    // The checkout summary starts collapsed on phones
    const resumo = $("[data-resumo-checkout]");
    if (resumo && window.matchMedia("(max-width: 1023px)").matches) {
      resumo.removeAttribute("open");
    }
  }

  /* --- Checkout: address choice ---------------------------------------- */
  function iniciarEntrega() {
    const formEndereco = $("[data-form-endereco]");
    if (!formEndereco) return;
    const radios = $$('input[name="endereco"][type="radio"]');
    radios.forEach((radio) =>
      radio.addEventListener("change", () => {
        const novo = radio.value === "novo";
        formEndereco.classList.toggle("js-escondido", !novo);
        if (novo) {
          formEndereco.querySelector("input")?.focus();
          return;
        }
        // A saved address was picked: recompute shipping for its CEP
        const form = radio.form;
        const acao = document.createElement("input");
        acao.type = "hidden";
        acao.name = "acao";
        acao.value = "atualizar";
        form.append(acao);
        form.submit();
      })
    );
  }

  function iniciar(raiz = document) {
    iniciarCarrosseis(raiz);
    iniciarCep(raiz);
  }

  document.addEventListener("DOMContentLoaded", () => {
    iniciar();
    iniciarGaleria();
    iniciarSeletorVariacao();
    iniciarQuantidades();
    iniciarCopiar();
    iniciarMenus();
    iniciarEntrega();
  });

  // Content swapped in by HTMX (filters, bag) gets the behaviors too
  document.addEventListener("htmx:afterSettle", (e) => iniciar(e.target));
})();
