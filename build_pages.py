# -*- coding: utf-8 -*-
"""Generate Evision service sub-pages + utility/legal pages, consistent with
the existing design system (service.css / chrome.js). Run: python build_pages.py"""
import html

VER = "?v=4"


def esc(s):
    return html.escape(s, quote=True)


def incl(icon, title, desc):
    return (f'<div class="incl"><div class="ic-wrap"><i data-lucide="{icon}" class="ic"></i></div>'
            f'<div><h3>{title}</h3><p>{desc}</p></div></div>')


def faq_item(i, q, a):
    return (f'<div class="faq-item"><button class="faq-q"><span class="faq-num">Q{i}</span>{q}'
            f'<span class="faq-ic"><i data-lucide="plus" style="width:18px;height:18px"></i></span></button>'
            f'<div class="faq-a"><div class="faq-a-inner">{a}</div></div></div>')


def rel(href, icon, title, sub):
    return (f'<a href="{href}" class="rel"><i data-lucide="{icon}" class="ic"></i>'
            f'<div><b>{title}</b><span>{sub}</span></div></a>')


# Parent category for the breadcrumb + URL chip (SEO / Content Marketing hubs).
SEO_CHILDREN = {"ai-seo", "llm-optimization", "agentic-ai-seo", "enterprise-seo",
                "ecommerce-seo", "technical-seo", "local-seo", "multilingual-seo",
                "link-building", "white-label-seo", "seo-audit"}
CONTENT_CHILDREN = {"guest-posting", "content-writing", "digital-pr"}


def parent_crumb(slug):
    if slug in SEO_CHILDREN:
        return ("SEO & AI Search", "seo.html", "seo")
    if slug in CONTENT_CHILDREN:
        return ("Content Marketing", "content-marketing.html", "content-marketing")
    return ("Services", "pricing.html", "services")


def service_page(slug, c):
    pname, phref, pslug = parent_crumb(slug)
    included = "\n          ".join(incl(*x) for x in c["included"])
    process = "\n          ".join(
        f'<li><h3>{t}</h3><p>{d}</p></li>' for t, d in c["process"])
    delivers = "\n          ".join(
        f'<li><i data-lucide="check-circle-2" class="ic"></i><span>{d}</span></li>' for d in c["deliverables"])
    faqs = "\n          ".join(faq_item(i + 1, q, a) for i, (q, a) in enumerate(c["faq"]))
    related = "\n      ".join(rel(*x) for x in c["related"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(c['title'])} | Evision Infoserve</title>
<meta name="description" content="{esc(c['metadesc'])}">
<link rel="stylesheet" href="assets/tokens.css{VER}">
<link rel="stylesheet" href="assets/site.css{VER}">
<link rel="stylesheet" href="assets/chrome.css{VER}">
<link rel="stylesheet" href="assets/service.css">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
</head>
<body data-page="services">

<!-- ░░ HERO ░░ -->
<section class="svc-hero">
  <div class="container svc-hero-inner">
    <nav class="crumb"><a href="index.html">Home</a><span class="sep">/</span><a href="{phref}">{esc(pname)}</a><span class="sep">/</span><span style="color:var(--color-gold-500)">{esc(c['name'])}</span></nav>
    <span class="eyebrow on-dark" style="margin-top:18px">{esc(c['eyebrow'])}</span>
    <h1>{esc(c['name'])}</h1>
    <p class="lead">{c['lead']}</p>
    <div class="hero-ctas" style="margin:26px 0 0;display:flex;gap:14px;flex-wrap:wrap">
      <a href="contact.html" data-audit-open class="btn btn-primary btn-lg">Get a Free Audit</a>
    </div>
    <div class="svc-meta-row">
      <span class="chip-mono"><i data-lucide="link" style="width:14px;height:14px"></i>/{pslug}/{slug}</span>
      <span class="chip-mono"><i data-lucide="code" style="width:14px;height:14px"></i>Service + FAQPage schema</span>
    </div>
  </div>
</section>

<!-- ░░ QUICK ANSWER ░░ -->
<section class="section-sm" style="background:var(--bg-subtle)">
  <div class="container">
    <div class="quick-answer reveal" style="max-width:880px">
      <div class="qa-head"><span class="qa-tag">QUICK ANSWER · AEO</span><span class="qa-q">{c['qa_q']}</span></div>
      <p>{c['qa_a']}</p>
    </div>
  </div>
</section>

<!-- ░░ BODY ░░ -->
<section class="section" style="padding-top:24px">
  <div class="container svc-layout">
    <div class="svc-main">
      <div class="svc-block" id="overview">
        <h2>{c['overview_h']}</h2>
        <p>{c['overview1']}</p>
        <p>{c['overview2']}</p>
      </div>

      <div class="svc-block" id="included">
        <h2>What's included</h2>
        <div class="incl-grid">
          {included}
        </div>
      </div>

      <div class="svc-block" id="process">
        <h2>How we deliver it</h2>
        <ul class="proc-list">
          {process}
        </ul>
      </div>

      <div class="svc-block" id="deliverables">
        <h2>What you'll receive</h2>
        <ul class="checks">
          {delivers}
        </ul>
      </div>

      <div class="svc-block" id="faq">
        <h2 style="margin-bottom:6px">Frequently asked questions</h2>
        <p style="margin-bottom:18px"><span class="chip-mono"><i data-lucide="code" style="width:14px;height:14px"></i>FAQPage schema applied</span></p>
        <div class="faq">
          {faqs}
        </div>
      </div>
    </div>

    <aside class="svc-side">
      <nav class="toc" data-toc>
        <h4>On this page</h4>
        <a href="#overview">Overview</a>
        <a href="#included">What's included</a>
        <a href="#process">How we deliver it</a>
        <a href="#deliverables">What you'll receive</a>
        <a href="#faq">FAQ</a>
      </nav>
      <div class="side-cta">
        <h4>{esc(c['side_title'])}</h4>
        <p>{c['side_text']}</p>
        <a href="contact.html" data-audit-open class="btn btn-primary btn-block">Get a Free Audit</a>
        <a href="https://wa.me/919811722064" class="btn btn-outline-white btn-block" style="margin-top:10px"><i data-lucide="message-circle" class="ic"></i>WhatsApp</a>
      </div>
      <div class="side-rate">
        <span class="stars"><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i></span>
        <div><b>4.7 / 5</b><small>2,124 Google reviews</small></div>
      </div>
    </aside>
  </div>

  <div class="container" style="margin-top:8px">
    <span class="eyebrow">Related services</span>
    <div class="rel-grid">
      {related}
    </div>
  </div>
</section>

<!-- ░░ PRICE ░░ -->
<section class="price-strip" data-price-slug="{slug}"></section>

<!-- ░░ CTA BAND ░░ -->
<section class="cta-band">
  <div class="container cta-inner">
    <div><h2 class="h-lg" style="color:#fff;max-width:22ch">{c['cta_h']}</h2><p class="lead" style="margin-top:12px;color:var(--fg-muted-dark)">Book a free audit this week — no obligation.</p></div>
    <a href="contact.html" data-audit-open class="btn btn-primary btn-lg">Get a Free Audit</a>
  </div>
</section>

<script src="assets/site.js{VER}"></script>
<script src="assets/chrome.js{VER}"></script>
<script src="assets/pricing.js{VER}"></script>
</body>
</html>
"""


# Reusable generic blocks to keep copy tight but consistent.
def G_PROCESS(audit, build, run_, report):
    return [("Audit & baseline", audit), ("Strategy & build", build),
            ("Execute", run_), ("Measure & iterate", report)]


SERVICES = {
 "ai-seo": dict(
   title="AI SEO Services", name="AI SEO", eyebrow="SEO · AI Search",
   metadesc="AI SEO from Evision Infoserve — optimise for Google AI Overviews and answer engines so your brand is the answer customers see.",
   lead="Optimise your site for Google's AI Overviews and answer engines — so you're the source customers see first.",
   qa_q="What is AI SEO?", qa_a="AI SEO is the practice of optimising content and technical signals so search engines' AI features — like Google AI Overviews — surface and cite your pages. It blends classic SEO foundations with answer-led content structuring.",
   overview_h="Rank in the answers, not just the links",
   overview1="Search results increasingly open with an AI-generated answer. AI SEO makes sure your brand is what that answer is built from — through clear, well-structured, authoritative content.",
   overview2="We combine entity optimisation, answer blocks and schema with strong technical foundations so you win both the AI panel and the traditional ranking beneath it.",
   included=[("sparkles","Answer-led content","Content structured so AI features can quote it cleanly."),
             ("code","Schema & entities","Structured data and entity consistency across your site."),
             ("search","Query coverage","Map and own the questions your buyers actually ask."),
             ("gauge","Technical health","Fast, crawlable pages AI systems can read."),
             ("eye","AI-panel tracking","Monitor where you appear in AI Overviews."),
             ("trending-up","Topical authority","Cluster content that proves depth on your topic.")],
   process=G_PROCESS("We baseline your visibility across Google and AI results.",
                     "Answer blocks, schema and entity work mapped to buyer queries.",
                     "We ship optimised content and technical fixes.",
                     "Monthly reporting on rankings and AI-panel presence."),
   deliverables=["An AI-visibility baseline report","Answer-optimised priority pages","Full schema & entity coverage","A query-to-content map","Monthly ranking + AI-panel report"],
   faq=[("Is AI SEO different from normal SEO?","It shares the same foundations but adds answer-structuring and entity work so AI features cite you — we run both together."),
        ("How long until I see results?","Technical and on-page wins can show in weeks; authority-driven AI citations typically build over 2–4 months."),
        ("Do you guarantee AI Overview placement?","No one can guarantee it, but structured, authoritative content measurably improves your odds — and we track it.")],
   related=[("seo.html","search","SEO & AI Search","The full programme"),("llm-optimization.html","bot","LLM Optimization","Get cited by AI"),("technical-seo.html","gauge","Technical SEO","Clean foundations")],
   side_title="Free AI-SEO audit", side_text="See how your site shows up across Google and AI answers today.",
   cta_h="Be the answer AI search shows your customers"),

 "llm-optimization": dict(
   title="LLM Optimization Services", name="LLM Optimization", eyebrow="SEO · LLMO",
   metadesc="LLM Optimization (LLMO) from Evision Infoserve — get your brand surfaced and cited inside ChatGPT, Gemini and Perplexity.",
   lead="Get your brand surfaced, summarised and cited inside ChatGPT, Gemini and Perplexity.",
   qa_q="What is LLM Optimization?", qa_a="LLM Optimization (LLMO) structures your content, entities and web presence so large language models reference your brand when users ask related questions — the AI-era equivalent of ranking #1.",
   overview_h="Win the chat box, not just the search box",
   overview1="More buyers now ask an AI assistant before they ever open Google. LLMO makes your brand part of those answers by giving models clean, consistent, quotable information about you.",
   overview2="We optimise content for citation, manage crawler access (llms.txt), strengthen your entity footprint, and monitor how models describe you.",
   included=[("bot","Citation-ready content","Clear, factual content models can quote with confidence."),
             ("file-text","llms.txt & crawler rules","Guide GPTBot, ClaudeBot & PerplexityBot to your best pages."),
             ("network","Entity footprint","Consistent brand facts across the web and knowledge graphs."),
             ("eye","Mention monitoring","Track how ChatGPT, Gemini & Perplexity describe you."),
             ("messages-square","Prompt coverage","Own the prompts your customers actually type."),
             ("shield-check","Accuracy control","Correct what AI gets wrong about your brand.")],
   process=G_PROCESS("We baseline how each major model currently describes you.",
                     "Citation content, llms.txt and entity work are planned.",
                     "We publish and structure content for model retrieval.",
                     "Monthly AI-mention tracking guides the next moves."),
   deliverables=["A baseline of AI mentions across models","Citation-optimised content","An llms.txt and crawler policy","Entity & knowledge-graph cleanup","A monthly AI-mention report"],
   faq=[("Can you really influence ChatGPT answers?","Yes — models retrieve and weight clear, authoritative, consistent sources. We make your brand exactly that, then measure mentions."),
        ("What is llms.txt?","A simple file that tells AI crawlers which content matters most — a growing best practice for AI visibility."),
        ("How do you measure success?","We track brand mentions and citations across ChatGPT, Gemini and Perplexity for your core queries over time.")],
   related=[("ai-seo.html","sparkles","AI SEO","AI Overviews"),("agentic-ai-seo.html","workflow","Agentic AI SEO","Automated SEO"),("content-marketing.html","pen-tool","Content Marketing","Citable content")],
   side_title="Free AI-visibility check", side_text="Find out whether AI assistants mention your brand — and what they say.",
   cta_h="Become the brand AI assistants recommend"),

 "agentic-ai-seo": dict(
   title="Agentic AI SEO Services", name="Agentic AI SEO", eyebrow="SEO · Automation",
   metadesc="Agentic AI SEO from Evision Infoserve — AI agents handle research, briefs and execution so your SEO moves faster at scale.",
   lead="AI agents handle research, briefs and execution — so your SEO programme moves faster, at scale.",
   qa_q="What is agentic AI SEO?", qa_a="Agentic AI SEO uses autonomous AI agents to run repetitive SEO work — keyword research, competitor analysis, content briefs and monitoring — supervised by strategists, so output scales without losing quality.",
   overview_h="SEO at machine speed, human judgement",
   overview1="Most SEO bottlenecks are research and production. We deploy AI agents to compress that work, then have senior strategists review and direct — giving you more output for the same budget.",
   overview2="From automated content briefs to continuous technical monitoring, agentic workflows keep your programme always-on.",
   included=[("workflow","Agent workflows","Autonomous research, briefs and reporting pipelines."),
             ("search","Continuous research","Always-on keyword and competitor intelligence."),
             ("file-text","Auto content briefs","Data-rich briefs your writers can run with."),
             ("gauge","Live monitoring","Agents watch rankings, indexation and breakages."),
             ("user-check","Human review","Strategists approve and direct everything agents produce."),
             ("trending-up","Faster iteration","Test and ship more changes every month.")],
   process=G_PROCESS("We map where automation adds the most leverage.",
                     "We configure agents and review gates for your site.",
                     "Agents execute; strategists supervise and refine.",
                     "Performance reporting tunes the agent workflows."),
   deliverables=["An automation opportunity map","Configured agent workflows","Automated briefs & research feeds","Continuous monitoring alerts","A monthly performance report"],
   faq=[("Is this just AI-generated spam content?","No — agents do research and drafting; humans edit, fact-check and approve. Quality and accuracy stay under our control."),
        ("Will Google penalise AI-assisted content?","Google rewards helpful content however it's made. We keep everything human-reviewed and genuinely useful."),
        ("What does the human role cover?","Strategy, review, fact-checking and final approval on every deliverable.")],
   related=[("ai-seo.html","sparkles","AI SEO","AI Overviews"),("llm-optimization.html","bot","LLM Optimization","Get cited"),("enterprise-seo.html","building","Enterprise SEO","At scale")],
   side_title="See where automation helps", side_text="A free audit of where agentic workflows can speed up your SEO.",
   cta_h="Scale your SEO without scaling your costs"),

 "enterprise-seo": dict(
   title="Enterprise SEO Services", name="Enterprise SEO", eyebrow="SEO · Enterprise",
   metadesc="Enterprise SEO from Evision Infoserve — scaled, governed SEO programmes for large sites, multiple teams and complex stacks.",
   lead="Scaled, governed SEO for large sites, multiple stakeholders and complex tech stacks.",
   qa_q="What is enterprise SEO?", qa_a="Enterprise SEO manages search across very large or complex websites — coordinating templates, governance, dev resources and reporting so thousands of pages improve consistently and safely.",
   overview_h="Move the needle across thousands of pages",
   overview1="On big sites, the wins are systemic: templates, internal linking, crawl budget and governance. We work at the pattern level so a single fix improves thousands of URLs.",
   overview2="We integrate with your dev and content teams, give stakeholders clear reporting, and put guardrails in place to protect rankings during releases.",
   included=[("layout-template","Template SEO","Fix patterns once, improve pages at scale."),
             ("git-branch","Crawl & architecture","Crawl-budget, internal linking and site structure."),
             ("users","Team enablement","Playbooks and training for content & dev teams."),
             ("shield-check","Release guardrails","Protect rankings through migrations and deploys."),
             ("bar-chart-3","Exec reporting","Dashboards stakeholders actually understand."),
             ("globe","Multi-market ready","Scale across regions and languages.")],
   process=G_PROCESS("A full technical and content audit at scale.",
                     "A prioritised, template-level roadmap and governance.",
                     "We execute with your teams and ship safely.",
                     "Executive dashboards track impact by segment."),
   deliverables=["An enterprise-scale audit","A template-level roadmap","SEO governance & guardrails","Team playbooks & training","Executive reporting dashboards"],
   faq=[("Do you work with our in-house team?","Yes — we plug into your content, dev and product workflows and enable your team rather than replace it."),
        ("Can you handle a site migration?","Absolutely — protecting rankings through replatforms and migrations is a core part of enterprise SEO."),
        ("How is success measured?","By segment-level organic growth, indexation health and pipeline impact — reported to stakeholders monthly.")],
   related=[("technical-seo.html","gauge","Technical SEO","Foundations"),("ecommerce-seo.html","shopping-cart","Ecommerce SEO","Revenue pages"),("multilingual-seo.html","globe","Multilingual SEO","Global reach")],
   side_title="Free enterprise SEO review", side_text="A scaled audit of your biggest template and crawl opportunities.",
   cta_h="Unlock compounding growth across your whole site"),

 "ecommerce-seo": dict(
   title="Ecommerce SEO Services", name="Ecommerce SEO", eyebrow="SEO · Ecommerce",
   metadesc="Ecommerce SEO from Evision Infoserve — category, product and collection SEO that drives qualified traffic and revenue.",
   lead="Category, product and collection-page SEO that drives qualified traffic and revenue.",
   qa_q="What is ecommerce SEO?", qa_a="Ecommerce SEO optimises online stores — category, product and collection pages, faceted navigation and schema — so shoppers find your products organically and convert.",
   overview_h="Turn search demand into sales",
   overview1="Most store revenue hides in category and collection pages. We optimise them for high-intent queries, fix faceted-navigation and duplication issues, and add rich product schema.",
   overview2="The result is more non-brand traffic landing on pages that are built to convert — not just to rank.",
   included=[("shopping-cart","Category & product SEO","Optimise the pages that actually sell."),
             ("filter","Faceted navigation","Tame filters, duplication and crawl waste."),
             ("code","Product schema","Rich results with price, stock and reviews."),
             ("search","Buyer-intent keywords","Target queries with purchase intent."),
             ("image","Image & feed SEO","Optimised images and shopping feeds."),
             ("gauge","Speed & Core Web Vitals","Fast pages that convert and rank.")],
   process=G_PROCESS("We audit your catalogue, templates and indexation.",
                     "Keyword-to-category mapping and a fix roadmap.",
                     "We optimise templates, content and schema.",
                     "Revenue and ranking reporting each month."),
   deliverables=["A catalogue & technical audit","Optimised category/product templates","Product & review schema","A keyword-to-page map","A monthly revenue + ranking report"],
   faq=[("Which platforms do you support?","Shopify, WooCommerce, Magento and custom stores — the principles and most fixes apply across all of them."),
        ("Can you fix duplicate product pages?","Yes — canonicalisation, faceted-nav rules and templating are core to ecommerce SEO and we handle them."),
        ("Do you optimise for Google Shopping too?","We optimise your product feed and images so they perform across organic and Shopping surfaces.")],
   related=[("technical-seo.html","gauge","Technical SEO","Foundations"),("local-seo.html","map-pin","Local SEO","Local stores"),("ppc.html","target","PPC & Paid Ads","Paid scale")],
   side_title="Free ecommerce SEO audit", side_text="Find the category and product pages losing you organic revenue.",
   cta_h="Grow store revenue from organic search"),

 "technical-seo": dict(
   title="Technical SEO Services", name="Technical SEO", eyebrow="SEO · Technical",
   metadesc="Technical SEO from Evision Infoserve — crawl, indexation, Core Web Vitals and schema fixed at the root for durable rankings.",
   lead="Crawl, indexation, Core Web Vitals and schema — fixed at the root for durable rankings.",
   qa_q="What is technical SEO?", qa_a="Technical SEO makes a site easy for search engines to crawl, render and index — covering site speed, Core Web Vitals, structured data, indexation and architecture, so your content can actually rank.",
   overview_h="Fix the foundations rankings depend on",
   overview1="Great content can't rank on a broken foundation. We find and fix the crawl, indexation, speed and structured-data issues holding your site back.",
   overview2="Every fix is prioritised by impact and shipped with your dev team, then verified — no guesswork.",
   included=[("gauge","Core Web Vitals","Diagnose and fix speed and stability issues."),
             ("git-branch","Crawl & indexation","Ensure the right pages are found and indexed."),
             ("code","Structured data","Schema that unlocks rich results."),
             ("sitemap","Architecture & linking","Logical structure and strong internal links."),
             ("smartphone","Mobile & rendering","Flawless mobile and JavaScript rendering."),
             ("shield-check","Migration safety","Protect rankings through site changes.")],
   process=G_PROCESS("A deep technical crawl and audit of your site.",
                     "A prioritised, dev-ready fix list with specs.",
                     "We implement (or guide your team) and verify.",
                     "Ongoing monitoring catches new issues early."),
   deliverables=["A full technical audit","A prioritised, dev-ready fix list","Core Web Vitals improvements","Complete schema coverage","Indexation & crawl monitoring"],
   faq=[("Will technical SEO alone improve rankings?","It removes the barriers holding you back and often lifts rankings on its own — paired with content, the gains compound."),
        ("Can you work with our developers?","Yes — we deliver clear specs and tickets, and can implement directly or guide your team."),
        ("How often should a technical audit run?","A deep audit yearly, with continuous monitoring in between to catch regressions fast.")],
   related=[("seo.html","search","SEO & AI Search","The full programme"),("enterprise-seo.html","building","Enterprise SEO","At scale"),("seo-audit.html","clipboard-check","SEO Audit","One-time check")],
   side_title="Free technical SEO audit", side_text="A crawl-level look at the issues capping your rankings.",
   cta_h="Build rankings on solid technical foundations"),

 "local-seo": dict(
   title="Local SEO Services", name="Local SEO", eyebrow="SEO · Local",
   metadesc="Local SEO from Evision Infoserve — Google Business Profile, map-pack rankings and local citations that bring nearby customers.",
   lead="Google Business Profile, map-pack rankings and citations that bring nearby customers in.",
   qa_q="What is local SEO?", qa_a="Local SEO helps a business rank for 'near me' and city-based searches — optimising your Google Business Profile, local landing pages, citations and reviews so you appear in the map pack.",
   overview_h="Own the map pack in your area",
   overview1="When people search for what you offer nearby, the map pack wins the click. We optimise your Google Business Profile, reviews and local pages to put you there.",
   overview2="Consistent citations, location pages and review velocity build the local trust signals Google rewards.",
   included=[("map-pin","Google Business Profile","Optimise and actively manage your GBP."),
             ("star","Review strategy","Earn and respond to reviews that build trust."),
             ("building-2","Location pages","High-quality pages for every area you serve."),
             ("list-checks","Citations & NAP","Consistent listings across local directories."),
             ("search","Local keywords","Target 'near me' and city-level intent."),
             ("message-circle","GBP posts & Q&A","Keep your profile active and answered.")],
   process=G_PROCESS("We audit your GBP, citations and local rankings.",
                     "A local content, review and citation plan.",
                     "We optimise listings, pages and reviews.",
                     "Map-pack and call/direction tracking monthly."),
   deliverables=["A local visibility audit","An optimised Google Business Profile","Local landing pages","Clean, consistent citations","A monthly local-ranking report"],
   faq=[("How long does local SEO take?","Profile and citation wins can show within weeks; competitive map-pack rankings usually build over 2–3 months."),
        ("Do reviews really affect rankings?","Yes — review quantity, quality and recency are strong local ranking and conversion signals."),
        ("Can you handle multiple locations?","Yes — we build and manage profiles and location pages for multi-branch businesses.")],
   related=[("seo.html","search","SEO & AI Search","The full programme"),("ecommerce-seo.html","shopping-cart","Ecommerce SEO","Online stores"),("orm.html","shield-check","ORM","Reviews & rep")],
   side_title="Free local SEO audit", side_text="See how you rank in the map pack — and how to climb it.",
   cta_h="Get found by customers right around you"),

 "multilingual-seo": dict(
   title="Multilingual SEO Services", name="Multilingual SEO Services", eyebrow="SEO · Global",
   metadesc="Multilingual SEO from Evision Infoserve — hreflang, localisation and SEO across languages and regions, done right.",
   lead="Hreflang, localisation and SEO across multiple languages and regions — done right.",
   qa_q="What is multilingual SEO?", qa_a="Multilingual SEO optimises a website for users in different languages and countries — using hreflang, localised content and regional signals so the right version ranks for the right audience.",
   overview_h="Rank in every market you serve",
   overview1="Translating pages isn't enough. We implement correct hreflang, localise content for intent (not just language), and align technical signals so each market sees the right version.",
   overview2="The outcome is clean international indexing and content that resonates locally — not a tangle of duplicate or mis-targeted pages.",
   included=[("globe","Hreflang setup","Correct language/region targeting at scale."),
             ("languages","Content localisation","Intent-matched copy, not literal translation."),
             ("git-branch","International architecture","ccTLD, subfolder or subdomain strategy."),
             ("search","In-market keywords","Research per language and region."),
             ("gauge","Technical hygiene","Avoid duplication and indexing conflicts."),
             ("map","Regional signals","Local trust and relevance per market.")],
   process=G_PROCESS("We audit your international setup and indexing.",
                     "A market, structure and hreflang strategy.",
                     "We localise content and implement targeting.",
                     "Per-market ranking and traffic reporting."),
   deliverables=["An international SEO audit","A correct hreflang implementation","Localised priority content","A per-market keyword map","Per-region performance reporting"],
   faq=[("Is translation the same as localisation?","No — localisation adapts intent, examples and search terms to each market. We optimise for how locals actually search."),
        ("Subfolders, subdomains or ccTLDs?","It depends on your goals and resources — we recommend the structure that fits your business and explain the trade-offs."),
        ("Can you fix broken hreflang?","Yes — mis-configured hreflang is one of the most common (and fixable) international SEO issues.")],
   related=[("enterprise-seo.html","building","Enterprise SEO","At scale"),("technical-seo.html","gauge","Technical SEO","Foundations"),("content-writing.html","pen-tool","Content Writing","Localised copy")],
   side_title="Free multilingual SEO audit", side_text="Check your hreflang and international setup for costly mistakes.",
   cta_h="Reach customers in every language that matters"),

 "link-building": dict(
   title="Link Building Services", name="Link Building Services", eyebrow="SEO · Authority",
   metadesc="Link building from Evision Infoserve — white-hat, relevant, authoritative backlinks that grow rankings safely.",
   lead="White-hat authority links from relevant, high-quality publishers — built to last.",
   qa_q="What is link building?", qa_a="Link building earns backlinks from other websites to yours. Quality, relevant links remain one of Google's strongest ranking signals — when built ethically rather than bought in bulk.",
   overview_h="Earn the authority Google rewards",
   overview1="Links still move rankings — but only the right ones. We earn relevant, editorial links through outreach, digital PR and genuinely useful content, never spammy networks.",
   overview2="Every link is vetted for relevance and authority, and reported transparently so you know exactly what you're getting.",
   included=[("link","Editorial outreach","Real placements on relevant, vetted sites."),
             ("file-text","Linkable assets","Content other sites want to reference."),
             ("search","Prospecting & vetting","Relevance and authority checked on every target."),
             ("shield-check","Safe, white-hat only","No PBNs, no spam, no risky shortcuts."),
             ("bar-chart-3","Transparent reporting","See every link, metric and anchor."),
             ("git-compare","Competitor gap analysis","Win the links your rivals rely on.")],
   process=G_PROCESS("We analyse your link profile and competitors.",
                     "A target list and linkable-asset plan.",
                     "We run outreach and earn placements.",
                     "Monthly link reports with metrics and anchors."),
   deliverables=["A backlink & competitor audit","A vetted target list","Earned editorial links","Linkable content assets","A transparent monthly link report"],
   faq=[("Are these links safe?","Yes — we only build relevant, editorial, white-hat links. We never use link farms or PBNs that risk penalties."),
        ("How many links per month?","Quality over quantity — volume depends on niche and budget, and we agree realistic targets up front."),
        ("Do you guarantee specific domains?","We target by relevance and authority and report every placement; exact domains depend on editorial acceptance.")],
   related=[("digital-pr.html","megaphone","Digital PR","Coverage & links"),("guest-posting.html","newspaper","Guest Posting","Placed articles"),("seo.html","search","SEO & AI Search","The full programme")],
   side_title="Free backlink audit", side_text="See your link profile and the gaps versus your competitors.",
   cta_h="Build the authority that lifts every page"),

 "white-label-seo": dict(
   title="White Label SEO Services", name="White Label SEO Services", eyebrow="SEO · For Agencies",
   metadesc="White label SEO from Evision Infoserve — full SEO delivery under your agency's brand, with reporting your clients love.",
   lead="Full SEO delivery under your agency's brand — reporting your clients will love.",
   qa_q="What is white label SEO?", qa_a="White label SEO is SEO fulfilment delivered by us under your agency's brand. You own the client relationship; we do the work and provide branded reports as if it were your own team.",
   overview_h="Add SEO to your agency — without the overhead",
   overview1="Offer expert SEO without hiring a team. We handle audits, on-page, technical, content and reporting behind the scenes, all under your brand.",
   overview2="You stay the trusted face to your clients; we're the engine room. Scale your services and margins without the hiring risk.",
   included=[("tag","Your branding","Reports and deliverables in your identity."),
             ("search","Full SEO fulfilment","Technical, on-page, content and links."),
             ("file-text","Branded reporting","Clear monthly reports you can forward."),
             ("users","Dedicated support","A consistent team that knows your accounts."),
             ("layout-template","Scalable delivery","Take on more clients with confidence."),
             ("lock","Total confidentiality","We stay invisible to your clients.")],
   process=G_PROCESS("We learn your processes, brand and client goals.",
                     "Scoped plans per client, in your templates.",
                     "We fulfil the work under your brand.",
                     "Branded monthly reports you simply forward."),
   deliverables=["Branded audits & reports","Full SEO fulfilment per client","On-page & technical execution","Content & link delivery","A dedicated delivery team"],
   faq=[("Will my clients know it's you?","No — everything is delivered under your brand and we never contact your clients directly."),
        ("How is it priced?","Wholesale per client or per package, so you set your own margin. We agree clear scopes up front."),
        ("Can you scale with us?","Yes — our delivery is built to add clients quickly without dropping quality.")],
   related=[("seo.html","search","SEO & AI Search","Core delivery"),("link-building.html","link","Link Building","Authority"),("content-writing.html","pen-tool","Content Writing","At scale")],
   side_title="Partner with us", side_text="Get a white-label proposal and sample report for your agency.",
   cta_h="Grow your agency's revenue with SEO we deliver"),

 "seo-audit": dict(
   title="SEO Audit Services", name="SEO Audit", eyebrow="SEO · Audit",
   metadesc="SEO Audit from Evision Infoserve — a 12-point technical, content and AI-visibility audit with a prioritised action plan.",
   lead="A 12-point technical, content and AI-visibility audit — with a prioritised action plan you can act on.",
   qa_q="What is an SEO audit?", qa_a="An SEO audit is a structured review of a website's technical health, content and authority — identifying what's holding rankings back and giving a prioritised plan to fix it.",
   overview_h="Know exactly what's holding you back",
   overview1="Before spending on SEO, you should know where you stand. Our audit reviews technical health, content, links and AI visibility, then ranks every issue by impact.",
   overview2="You get a clear, prioritised action plan — usable by us or your own team — with no obligation to continue.",
   included=[("gauge","Technical health","Crawl, indexation, speed and Core Web Vitals."),
             ("file-text","Content review","Gaps, quality and keyword coverage."),
             ("link","Backlink analysis","Authority and toxic-link check."),
             ("eye","AI-visibility check","How AI engines see and cite you."),
             ("git-compare","Competitor benchmark","Where you stand versus rivals."),
             ("list-checks","Prioritised actions","A ranked, do-this-next roadmap.")],
   process=[("Discovery","We confirm your goals, markets and competitors."),
            ("Deep analysis","We crawl and review technical, content and links."),
            ("AI-visibility scan","We check your presence across AI engines."),
            ("Action plan","You get a prioritised, plain-English roadmap.")],
   deliverables=["A 12-point audit report","A prioritised action plan","Technical issue list with severity","Content & keyword-gap findings","A competitor benchmark"],
   faq=[("Is the audit really one-time?","Yes — it's a standalone deliverable. You can act on it yourself or have us implement it; there's no obligation."),
        ("How long does it take?","Most audits are delivered within 3–5 working days, depending on site size."),
        ("What do I get at the end?","A clear report plus a prioritised, plain-English action plan you can hand to any team.")],
   related=[("technical-seo.html","gauge","Technical SEO","Fix the issues"),("seo.html","search","SEO & AI Search","Ongoing growth"),("ai-seo.html","sparkles","AI SEO","AI Overviews")],
   side_title="Get your audit", side_text="Request your 12-point SEO + AI-visibility audit today.",
   cta_h="Start with a clear, honest picture of your SEO"),

 "guest-posting": dict(
   title="Guest Posting Services", name="Guest Posting", eyebrow="Content · Outreach",
   metadesc="Guest posting from Evision Infoserve — editorially placed articles on relevant, authoritative sites that build links and reach.",
   lead="Editorially placed articles on relevant, authoritative sites — for links, referral traffic and reach.",
   qa_q="What is guest posting?", qa_a="Guest posting publishes your articles on other relevant, authoritative websites — earning contextual backlinks, referral traffic and brand exposure to new audiences.",
   overview_h="Get published where your audience already reads",
   overview1="We secure genuine editorial placements on sites your buyers trust — written well, relevant to the host, and valuable to readers.",
   overview2="Every placement is vetted for relevance and real audience, so you build authority and traffic, not just a link count.",
   included=[("newspaper","Vetted placements","Relevant, real-audience sites only."),
             ("pen-tool","Editorial writing","Articles worthy of the host publication."),
             ("link","Contextual links","Natural links back to your key pages."),
             ("search","Topic & site research","Targets matched to your niche."),
             ("shield-check","Quality control","No spam networks or fake blogs."),
             ("bar-chart-3","Transparent reporting","Every placement, link and metric shown.")],
   process=G_PROCESS("We define topics, targets and link goals.",
                     "We pitch and secure editorial placements.",
                     "We write and publish high-quality articles.",
                     "Monthly reporting on placements and links."),
   deliverables=["A vetted target-site list","Editorially written articles","Contextual, relevant backlinks","Placement on real-audience sites","A transparent monthly report"],
   faq=[("Are these paid or editorial placements?","We prioritise genuine editorial relevance and real audiences — never low-quality paid link farms."),
        ("Do you write the articles?","Yes — our writers produce content tailored to each host publication and your goals."),
        ("How many placements per month?","It depends on niche and budget; we agree realistic, quality-first targets up front.")],
   related=[("link-building.html","link","Link Building","Authority links"),("digital-pr.html","megaphone","Digital PR","Press coverage"),("content-writing.html","pen-tool","Content Writing","On-site content")],
   side_title="Free placement plan", side_text="Get a sample list of sites we could place you on.",
   cta_h="Get published on sites your customers trust"),

 "content-writing": dict(
   title="Content Writing Services", name="Content Writing Services", eyebrow="Content · Writing",
   metadesc="Content writing from Evision Infoserve — SEO-led blogs, web copy and landing pages written to rank and convert.",
   lead="SEO-led blogs, web copy and landing pages — written to rank and to convert.",
   qa_q="What are content writing services?", qa_a="Content writing services produce written content — blogs, web pages, landing pages and more — optimised for search intent and crafted to persuade readers to act.",
   overview_h="Words that rank — and sell",
   overview1="Content only works when it does both jobs: satisfy search intent and move the reader. Our writers blend SEO research with persuasive, on-brand copy.",
   overview2="From topic clusters to high-converting landing pages, every piece is briefed with data and edited to a high standard.",
   included=[("pen-tool","SEO blog writing","Research-backed articles that rank."),
             ("layout","Web & landing copy","Pages structured to convert."),
             ("search","Keyword-led briefs","Intent-mapped, data-driven briefs."),
             ("layers","Topic clusters","Content that builds topical authority."),
             ("check-circle-2","Editing & QA","Polished, accurate, on-brand copy."),
             ("sparkles","AEO-ready structure","Answer blocks AI engines can cite.")],
   process=G_PROCESS("We research intent and plan a content calendar.",
                     "Data-driven briefs map keywords to pages.",
                     "We write, edit and optimise each piece.",
                     "Performance reporting shapes the next batch."),
   deliverables=["A keyword-led content calendar","SEO-optimised articles & pages","Conversion-focused landing copy","Editing and quality assurance","A monthly content performance report"],
   faq=[("Is the content original?","Yes — every piece is original, researched and edited by people. We never publish spun or duplicated content."),
        ("Do you optimise for SEO?","Always — each piece starts from a keyword-and-intent brief and is structured to rank and to be cited by AI engines."),
        ("Can you match our brand voice?","Yes — we build a voice guide and write to it consistently across everything.")],
   related=[("content-marketing.html","pen-tool","Content Marketing","Full strategy"),("guest-posting.html","newspaper","Guest Posting","Off-site content"),("seo.html","search","SEO & AI Search","Make it rank")],
   side_title="Free content sample", side_text="Get a sample brief and outline for one of your key pages.",
   cta_h="Publish content that ranks and converts"),

 "digital-pr": dict(
   title="Digital PR Services", name="Digital PR", eyebrow="Content · PR",
   metadesc="Digital PR from Evision Infoserve — newsworthy campaigns that earn coverage, authority links and brand mentions.",
   lead="Newsworthy campaigns that earn coverage, authoritative links and brand mentions.",
   qa_q="What is digital PR?", qa_a="Digital PR earns media coverage and high-authority backlinks by creating newsworthy stories, data studies and expert commentary that journalists and publishers want to feature.",
   overview_h="Earn the coverage money can't buy",
   overview1="The strongest links and brand lift come from genuine press coverage. We craft data-led stories and expert angles, then pitch them to relevant journalists and publications.",
   overview2="The payoff is authority links, brand mentions and trust — assets that compound for your SEO and reputation alike.",
   included=[("megaphone","Story & angle creation","Newsworthy hooks journalists want."),
             ("bar-chart-3","Data-led campaigns","Original research that earns coverage."),
             ("mail","Media outreach","Pitching to relevant, vetted journalists."),
             ("link","Authority links","High-trust coverage and backlinks."),
             ("quote","Expert commentary","Position your team as go-to sources."),
             ("trending-up","Coverage reporting","Track placements, links and reach.")],
   process=G_PROCESS("We find angles and data with newsroom appeal.",
                     "We build the campaign asset and media list.",
                     "We pitch and secure coverage.",
                     "We report coverage, links and brand reach."),
   deliverables=["A campaign concept & assets","A targeted media list","Secured press coverage","High-authority backlinks","A coverage & impact report"],
   faq=[("How is digital PR different from link building?","Digital PR earns links through genuine news coverage and stories, which also build brand and trust — not just standalone links."),
        ("Do you guarantee coverage?","Coverage depends on editorial interest, so we don't promise specific outlets — but strong, data-led stories reliably land placements."),
        ("What makes a story newsworthy?","Original data, timeliness, a strong human or local angle, and genuine relevance to the outlet's readers.")],
   related=[("link-building.html","link","Link Building","Authority links"),("guest-posting.html","newspaper","Guest Posting","Placed articles"),("orm.html","shield-check","ORM","Reputation")],
   side_title="Free digital PR ideas", side_text="Get a couple of campaign angles tailored to your brand.",
   cta_h="Earn the press coverage that builds authority"),
}


# ── Simple pages (utility + legal) ──
def simple_page(slug, c):
    body = c["body"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(c['title'])} | Evision Infoserve</title>
<meta name="description" content="{esc(c['metadesc'])}">
<link rel="stylesheet" href="assets/tokens.css{VER}">
<link rel="stylesheet" href="assets/site.css{VER}">
<link rel="stylesheet" href="assets/chrome.css{VER}">
<link rel="stylesheet" href="assets/service.css">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
</head>
<body data-page="{c.get('page','')}">

<section class="svc-hero">
  <div class="container svc-hero-inner">
    <nav class="crumb"><a href="index.html">Home</a><span class="sep">/</span><span style="color:var(--color-gold-500)">{esc(c['name'])}</span></nav>
    <span class="eyebrow on-dark" style="margin-top:18px">{esc(c['eyebrow'])}</span>
    <h1>{esc(c['name'])}</h1>
    <p class="lead">{c['lead']}</p>
  </div>
</section>

<section class="section">
  <div class="container" style="max-width:880px">
    {body}
  </div>
</section>

<!-- ░░ CTA BAND ░░ -->
<section class="cta-band">
  <div class="container cta-inner">
    <div><h2 class="h-lg" style="color:#fff;max-width:22ch">Ready to grow with Evision?</h2><p class="lead" style="margin-top:12px;color:var(--fg-muted-dark)">Book a free audit this week — no obligation.</p></div>
    <a href="contact.html" data-audit-open class="btn btn-primary btn-lg">Get a Free Audit</a>
  </div>
</section>

<script src="assets/site.js{VER}"></script>
<script src="assets/chrome.js{VER}"></script>
<script src="assets/pricing.js{VER}"></script>
</body>
</html>
"""


def policy_body(intro, sections):
    out = [f'<p style="color:var(--fg-muted-light);margin-bottom:8px">Last updated: June 2026</p>', f'<p>{intro}</p>']
    for h, p in sections:
        out.append(f'<h2 style="margin-top:28px">{h}</h2><p>{p}</p>')
    return "\n    ".join(out)


SIMPLE = {
 "portfolio": dict(
   title="Portfolio & Case Studies", name="Portfolio & Case Studies", eyebrow="Our work", page="",
   metadesc="Evision Infoserve portfolio and case studies — real results from SEO, AI search, content and paid campaigns.",
   lead="A selection of results we've delivered across SEO, AI search, content and paid media.",
   body="""<div class="incl-grid">
      <div class="incl"><div class="ic-wrap"><i data-lucide="trending-up" class="ic"></i></div><div><h3>SaaS · +212% organic</h3><p>Doubled non-brand traffic in 7 months with technical fixes and topic clusters.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="shopping-cart" class="ic"></i></div><div><h3>Ecommerce · +after AI Overviews</h3><p>Category-page SEO grew revenue from organic by 64% year on year.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="map-pin" class="ic"></i></div><div><h3>Local services · map-pack #1</h3><p>From page two to the top of the local pack across 9 service areas.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="bot" class="ic"></i></div><div><h3>B2B · cited by AI</h3><p>Became a cited source in ChatGPT and Perplexity for core category queries.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="megaphone" class="ic"></i></div><div><h3>D2C · digital PR</h3><p>A data study earned 40+ pieces of coverage and high-authority links.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="target" class="ic"></i></div><div><h3>Lead-gen · −38% CPL</h3><p>Restructured paid campaigns to cut cost-per-lead while scaling volume.</p></div></div>
    </div>
    <p style="margin-top:24px">Want the full case study for your industry? <a href="contact.html" data-audit-open>Ask us for relevant examples</a> and we'll share detailed results.</p>"""),

 "clients": dict(
   title="Our Clients", name="Our Clients", eyebrow="Who we work with", page="",
   metadesc="The brands that trust Evision Infoserve for SEO, AI search and digital marketing across India and beyond.",
   lead="From local businesses to funded startups and enterprises — here's who we help grow.",
   body="""<p>We partner with ambitious brands across SaaS, ecommerce, healthcare, education, real estate, professional services and D2C. Whether you're a single-location business or a multi-market enterprise, we tailor the programme to your goals.</p>
    <div class="incl-grid" style="margin-top:22px">
      <div class="incl"><div class="ic-wrap"><i data-lucide="building-2" class="ic"></i></div><div><h3>Startups & SaaS</h3><p>Scalable organic growth engines built for the long term.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="shopping-cart" class="ic"></i></div><div><h3>Ecommerce & D2C</h3><p>Category and product SEO that drives real revenue.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="stethoscope" class="ic"></i></div><div><h3>Healthcare & clinics</h3><p>Local and trust-led visibility that books appointments.</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="briefcase" class="ic"></i></div><div><h3>Professional services</h3><p>Authority content that wins high-value enquiries.</p></div></div>
    </div>
    <p style="margin-top:24px">Curious whether we've worked in your niche? <a href="contact.html" data-audit-open>Get in touch</a> — we'll share relevant results.</p>"""),

 "career": dict(
   title="Careers", name="Careers", eyebrow="Join the team", page="",
   metadesc="Careers at Evision Infoserve — join a Greater Noida digital marketing team building for the AI-search era.",
   lead="We're building the agency for the AI-search era — and we're always glad to meet sharp, curious people.",
   body="""<p>At Evision Infoserve you'll work on real challenges across SEO, AI search (GEO/LLMO), content and paid media, with senior mentorship and room to grow fast.</p>
    <h2 style="margin-top:28px">Open roles</h2>
    <div class="incl-grid" style="margin-top:12px">
      <div class="incl"><div class="ic-wrap"><i data-lucide="search" class="ic"></i></div><div><h3>SEO Executive</h3><p>1–3 yrs · Greater Noida / hybrid</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="pen-tool" class="ic"></i></div><div><h3>Content Writer</h3><p>0–2 yrs · Greater Noida / remote</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="target" class="ic"></i></div><div><h3>Performance Marketer</h3><p>2–4 yrs · Greater Noida</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="bot" class="ic"></i></div><div><h3>AI SEO Specialist</h3><p>2+ yrs · Greater Noida / hybrid</p></div></div>
    </div>
    <p style="margin-top:24px">Don't see your role? We still want to hear from great people. Email your CV to <a href="mailto:info@evisioninfoserve.com">info@evisioninfoserve.com</a> or <a href="contact.html" data-audit-open>say hello</a>.</p>"""),

 "testimonials": dict(
   title="Testimonials & Reviews", name="Testimonials & Reviews", eyebrow="What clients say", page="",
   metadesc="Read what Evision Infoserve clients say — 4.7/5 across 2,000+ reviews for SEO, AI search and digital marketing.",
   lead="Rated 4.7 / 5 across 2,000+ reviews. Here's what working with us is like.",
   body="""<div class="incl-grid">
      <div class="incl"><div class="ic-wrap"><i data-lucide="quote" class="ic"></i></div><div><h3>Ankit · SaaS founder</h3><p>"Organic became our biggest channel within two quarters. Clear reporting, real results."</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="quote" class="ic"></i></div><div><h3>Priya · Ecommerce</h3><p>"They fixed issues three agencies missed. Category traffic and revenue both up."</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="quote" class="ic"></i></div><div><h3>Rahul · Clinic owner</h3><p>"We're #1 in the map pack now and the phone hasn't stopped. Brilliant local SEO."</p></div></div>
      <div class="incl"><div class="ic-wrap"><i data-lucide="quote" class="ic"></i></div><div><h3>Meera · Marketing head</h3><p>"The only team that actually understands AI search. We're cited in ChatGPT now."</p></div></div>
    </div>
    <p style="margin-top:24px">Want references in your industry? <a href="contact.html" data-audit-open>Ask us</a> — we're happy to connect you with relevant clients.</p>"""),

 "privacy-policy": dict(
   title="Privacy Policy", name="Privacy Policy", eyebrow="Legal", page="",
   metadesc="Evision Infoserve privacy policy — how we collect, use and protect your personal data.",
   lead="How we collect, use and protect your information.",
   body=policy_body(
     "This Privacy Policy explains how Evision Infoserve (\"we\", \"us\") collects and uses information when you use our website or services.",
     [("Information we collect","We collect details you submit through our forms — such as your name, email, phone number, company and message — plus standard analytics data like pages visited and device type."),
      ("How we use it","We use your information to respond to enquiries, deliver and improve our services, send updates you've opted into, and meet legal obligations."),
      ("Marketing communications","If you opt in, we may email you tips, offers and updates. You can unsubscribe at any time using the link in any email."),
      ("Cookies & analytics","We use cookies and analytics tools to understand how the site is used and to improve it. You can control cookies through your browser settings."),
      ("Data sharing","We do not sell your data. We share it only with trusted providers who help us operate (e.g. email and analytics), under appropriate safeguards."),
      ("Data security","We use reasonable technical and organisational measures to protect your data. No method of transmission is 100% secure, but we take protection seriously."),
      ("Your rights","You may request access to, correction of, or deletion of your personal data. Contact us and we'll respond promptly."),
      ("Contact","Questions about this policy? Email info@evisioninfoserve.com or call +91 98117 22064.")])),

 "refund-policy": dict(
   title="Refund Policy", name="Refund Policy", eyebrow="Legal", page="",
   metadesc="Evision Infoserve refund policy — terms for refunds on our digital marketing services.",
   lead="Our approach to refunds and cancellations.",
   body=policy_body(
     "This Refund Policy applies to services purchased from Evision Infoserve. Because our work involves dedicated time and resources, please read it carefully.",
     [("Service-based work","SEO, content, PPC and related services are delivered as ongoing or project-based work. Fees cover time and resources already committed to your account."),
      ("Monthly retainers","Retainers are billed in advance for the month. You may cancel with notice as set out in your agreement; work already performed in the current cycle is non-refundable."),
      ("One-time projects","For one-time deliverables (such as an SEO audit), a refund may be available only before work has commenced. Once work begins, fees are non-refundable."),
      ("How to request","To request a refund or cancellation, email info@evisioninfoserve.com with your details. We'll review and respond within 7 working days."),
      ("Exceptions","Where we have clearly failed to deliver an agreed deliverable, we'll first work to make it right, and consider a fair partial refund if we cannot."),
      ("Contact","For any billing question, email info@evisioninfoserve.com or call +91 98117 22064.")])),

 "terms": dict(
   title="Terms and Conditions", name="Terms and Conditions", eyebrow="Legal", page="",
   metadesc="Evision Infoserve terms and conditions for using our website and services.",
   lead="The terms that govern your use of our website and services.",
   body=policy_body(
     "These Terms and Conditions govern your use of the Evision Infoserve website and the services we provide. By using our site or engaging us, you agree to these terms.",
     [("Use of our website","You may use this site for lawful purposes only. You agree not to misuse it, attempt unauthorised access, or disrupt its operation."),
      ("Services & proposals","Specific services, deliverables, timelines and fees are set out in individual proposals or agreements, which take precedence where they differ from general information on this site."),
      ("Quotes & pricing","Prices shown on this site are indicative starting points and may change. A confirmed quote is provided after we understand your requirements."),
      ("Client responsibilities","You agree to provide timely access, information and approvals needed to deliver the work, and to ensure content you supply does not infringe third-party rights."),
      ("Intellectual property","Site content is owned by Evision Infoserve. Deliverables we create transfer to you as set out in your agreement, typically on full payment."),
      ("Limitation of liability","We deliver services with reasonable skill and care but do not guarantee specific rankings or results. Our liability is limited to the fees paid for the relevant service."),
      ("Changes","We may update these terms from time to time. Continued use of the site means you accept the current version."),
      ("Contact","Questions about these terms? Email info@evisioninfoserve.com or call +91 98117 22064.")])),
}


def main():
    written = []
    for slug, c in SERVICES.items():
        c.setdefault("overview_h", c["name"])
        open(slug + ".html", "w", encoding="utf-8", newline="\n").write(service_page(slug, c))
        written.append(slug + ".html")
    for slug, c in SIMPLE.items():
        open(slug + ".html", "w", encoding="utf-8", newline="\n").write(simple_page(slug, c))
        written.append(slug + ".html")
    print("Wrote %d pages:" % len(written))
    for w in written:
        print("  ", w)


if __name__ == "__main__":
    main()
