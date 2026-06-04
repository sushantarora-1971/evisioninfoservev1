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
    if not href.startswith(('/', 'http')):
        href = '/' + href
    return (f'<a href="{href}" class="rel"><i data-lucide="{icon}" class="ic"></i>'
            f'<div><b>{title}</b><span>{sub}</span></div></a>')


# Parent category for the breadcrumb + URL chip (SEO / Content Marketing hubs).
SEO_CHILDREN = {"ai-seo", "llm-optimization", "agentic-ai-seo", "enterprise-seo",
                "ecommerce-seo", "technical-seo", "local-seo", "multilingual-seo",
                "link-building", "white-label-seo", "seo-audit", "industry-seo"}
CONTENT_CHILDREN = {"guest-posting", "content-writing", "digital-pr"}


def parent_crumb(slug):
    if slug in SEO_CHILDREN:
        return ("SEO Services", "/services/seo", "services/seo")
    if slug in CONTENT_CHILDREN:
        return ("Content Marketing", "/services/content-marketing", "services/content-marketing")
    return ("Services", "/pricing", "services")


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
<meta name="robots" content="noindex, nofollow"><!-- DEV PHASE: remove before launch -->
<title>{esc(c['title'])} | Evision Infoserve</title>
<meta name="description" content="{esc(c['metadesc'])}">
<link rel="stylesheet" href="/assets/tokens.css{VER}">
<link rel="stylesheet" href="/assets/site.css{VER}">
<link rel="stylesheet" href="/assets/chrome.css{VER}">
<link rel="stylesheet" href="/assets/service.css">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
</head>
<body data-page="services">

<!-- ░░ HERO ░░ -->
<section class="svc-hero">
  <div class="container svc-hero-inner">
    <nav class="crumb"><a href="/index.html">Home</a><span class="sep">/</span><a href="{phref}">{esc(pname)}</a><span class="sep">/</span><span style="color:var(--color-gold-500)">{esc(c['name'])}</span></nav>
    <span class="eyebrow on-dark" style="margin-top:18px">{esc(c['eyebrow'])}</span>
    <h1>{esc(c['name'])}</h1>
    <p class="lead">{c['lead']}</p>
    <div class="hero-ctas" style="margin:26px 0 0;display:flex;gap:14px;flex-wrap:wrap">
      <a href="/contact.html" data-audit-open class="btn btn-primary btn-lg">Get a Free Audit</a>
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
        <a href="/contact.html" data-audit-open class="btn btn-primary btn-block">Get a Free Audit</a>
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
    <a href="/contact.html" data-audit-open class="btn btn-primary btn-lg">Get a Free Audit</a>
  </div>
</section>

<script src="/assets/site.js{VER}"></script>
<script src="/assets/chrome.js{VER}"></script>
<script src="/assets/pricing.js{VER}"></script>
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
   faq=[("What is AI SEO?","AI SEO uses artificial intelligence to optimize content, identify ranking opportunities, and improve search visibility across modern search platforms."),
        ("How does AI SEO differ from traditional SEO?","AI SEO leverages machine learning, predictive analysis, and automation to improve efficiency and content performance."),
        ("Can AI SEO improve content quality?","Yes. AI tools can analyze search intent, identify content gaps, and recommend improvements that enhance relevance and engagement."),
        ("Does AI SEO help with AI search engines?","Yes. AI SEO helps businesses become more discoverable in AI-powered search experiences and generative search results."),
        ("Which businesses benefit most from AI SEO?","Ecommerce brands, SaaS companies, enterprises, agencies, and content-driven businesses benefit significantly from AI SEO."),
        ("Is AI SEO replacing traditional SEO?","No. AI SEO enhances traditional SEO strategies rather than replacing them."),
        ("Why is AI SEO important for future search visibility?","As AI-driven search adoption grows, AI SEO helps businesses maintain visibility, authority, and digital competitiveness.")],
   related=[("seo.html","search","SEO Services","The full programme"),("llm-optimization.html","bot","LLM Optimization","Get cited by AI"),("technical-seo.html","gauge","Technical SEO","Clean foundations")],
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
   faq=[("What is LLM Optimization?","LLM Optimization improves content visibility within AI platforms, generative search engines, and large language model responses."),
        ("Why is LLM Optimization important?","It increases the chances of brand mentions, citations, and recommendations in AI-generated answers."),
        ("How does LLM Optimization work?","It focuses on structured content, topical authority, factual accuracy, and semantic relevance."),
        ("Can LLM Optimization improve AI citations?","Yes. Optimized content is more likely to be referenced and cited by AI search systems."),
        ("What types of websites need LLM Optimization?","Business websites, SaaS companies, ecommerce stores, publishers, and educational platforms benefit greatly."),
        ("Is LLM Optimization different from SEO?","Yes. While related, LLM Optimization focuses specifically on AI models and conversational search experiences."),
        ("What are the benefits of LLM Optimization?","Improved AI visibility, higher brand authority, increased citations, and stronger digital presence.")],
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
   faq=[("What is Agentic AI SEO?","Agentic AI SEO uses autonomous AI agents to analyze, optimize, monitor, and improve search performance continuously."),
        ("How does Agentic AI SEO work?","AI agents automate keyword research, content optimization, competitor analysis, and performance monitoring."),
        ("Can Agentic AI SEO improve rankings faster?","It helps identify opportunities and automate repetitive tasks, improving SEO efficiency and scalability."),
        ("Who should use Agentic AI SEO?","Large businesses, agencies, ecommerce brands, and enterprises seeking advanced automation."),
        ("Is Agentic AI SEO suitable for small businesses?","Yes, especially businesses looking to scale content and optimization efforts efficiently."),
        ("Does Agentic AI SEO replace human experts?","No. It supports SEO professionals by automating tasks and providing actionable insights."),
        ("What are the benefits of Agentic AI SEO?","Improved efficiency, faster optimization, scalable growth, and better decision-making.")],
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
   faq=[("What is Enterprise SEO?","Enterprise SEO manages search optimization for large websites with thousands of pages and complex structures."),
        ("Who needs Enterprise SEO?","Large corporations, ecommerce platforms, publishers, and multi-location businesses."),
        ("What makes Enterprise SEO different?","It focuses on scalability, automation, governance, and advanced technical SEO."),
        ("Can Enterprise SEO improve global visibility?","Yes. It helps organizations optimize multiple websites, languages, and regions."),
        ("Why is technical SEO important in Enterprise SEO?","Large websites require efficient crawling, indexing, and site architecture management."),
        ("How does Enterprise SEO support business growth?","It drives large-scale organic traffic and increases brand visibility."),
        ("What are common Enterprise SEO challenges?","Managing content, technical complexity, multiple stakeholders, and large-scale optimization.")],
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
   faq=[("What is Ecommerce SEO?","Ecommerce SEO optimizes online stores to increase visibility, traffic, and sales."),
        ("Why is Ecommerce SEO important?","It helps customers discover products through organic search."),
        ("Which pages should be optimized?","Product pages, category pages, collections, blogs, and landing pages."),
        ("Can Ecommerce SEO increase sales?","Yes. Higher rankings attract qualified buyers and improve conversions."),
        ("What keywords should ecommerce stores target?","Product, category, transactional, and long-tail keywords."),
        ("Does Ecommerce SEO help reduce ad spend?","Yes. Organic traffic can lower customer acquisition costs over time."),
        ("How often should ecommerce websites be optimized?","SEO should be monitored and improved continuously.")],
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
   faq=[("What is Technical SEO?","Technical SEO improves website infrastructure for search engine crawling and indexing."),
        ("Why is Technical SEO important?","Without technical optimization, search engines may struggle to understand website content."),
        ("What does Technical SEO include?","Site speed, mobile optimization, structured data, crawlability, and indexing improvements."),
        ("Can Technical SEO improve rankings?","Yes. It strengthens the foundation for better search visibility."),
        ("How does page speed affect SEO?","Faster websites improve user experience and search performance."),
        ("What is schema markup?","Schema markup helps search engines understand content and display rich results."),
        ("How often should Technical SEO audits be performed?","At least every 3–6 months.")],
   related=[("seo.html","search","SEO Services","The full programme"),("enterprise-seo.html","building","Enterprise SEO","At scale"),("seo-audit.html","clipboard-check","SEO Audit","One-time check")],
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
   faq=[("What is Local SEO?","Local SEO helps businesses appear in local search results and map listings."),
        ("Why is Local SEO important?","It attracts nearby customers actively searching for products or services."),
        ("What is Google Business Profile optimization?","It improves visibility in Google Maps and local searches."),
        ("Which businesses need Local SEO?","Clinics, restaurants, schools, agencies, and service providers."),
        ("How do reviews affect Local SEO?","Positive reviews improve credibility and local rankings."),
        ("Can Local SEO increase phone calls?","Yes. It helps businesses appear for high-intent local searches."),
        ("How long does Local SEO take?","Many businesses see improvements within a few months.")],
   related=[("seo.html","search","SEO Services","The full programme"),("ecommerce-seo.html","shopping-cart","Ecommerce SEO","Online stores"),("orm.html","shield-check","ORM","Reviews & rep")],
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
   faq=[("What is Multilingual SEO?","Multilingual SEO optimizes websites for multiple languages and regions."),
        ("Why is Multilingual SEO important?","It helps businesses reach international audiences."),
        ("What is hreflang implementation?","Hreflang tags help search engines serve the correct language version."),
        ("Can Multilingual SEO improve global traffic?","Yes. It increases visibility in international markets."),
        ("Which businesses benefit from Multilingual SEO?","Global brands, ecommerce stores, educational institutions, and travel companies."),
        ("Is translation enough for Multilingual SEO?","No. Content must be localized for each audience."),
        ("How does Multilingual SEO improve user experience?","Visitors receive content in their preferred language.")],
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
   faq=[("What is link building?","Link building acquires backlinks from reputable websites."),
        ("Why are backlinks important?","Backlinks signal trust and authority to search engines."),
        ("Do all backlinks improve SEO?","No. High-quality backlinks provide the most value."),
        ("What are white-hat link-building strategies?","Guest posting, digital PR, resource outreach, and content marketing."),
        ("Can link building improve rankings?","Yes. Strong backlinks remain a major ranking factor."),
        ("How long does link building take?","Results typically develop over several months."),
        ("Is link building safe?","Yes, when ethical SEO practices are followed.")],
   related=[("digital-pr.html","megaphone","Digital PR","Coverage & links"),("guest-posting.html","newspaper","Guest Posting","Placed articles"),("seo.html","search","SEO Services","The full programme")],
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
   faq=[("What is White Label SEO?","White Label SEO allows agencies to resell SEO services under their brand."),
        ("Who uses White Label SEO?","Marketing agencies, consultants, and web development companies."),
        ("What are the benefits of White Label SEO?","Scalability, expertise, and expanded service offerings."),
        ("Does White Label SEO include reporting?","Yes. Most providers offer branded reports."),
        ("Can agencies retain client ownership?","Yes. Agencies maintain client relationships."),
        ("Is White Label SEO cost-effective?","It reduces hiring and operational expenses."),
        ("How does White Label SEO support agency growth?","It enables agencies to expand without increasing internal resources.")],
   related=[("seo.html","search","SEO Services","Core delivery"),("link-building.html","link","Link Building","Authority"),("content-writing.html","pen-tool","Content Writing","At scale")],
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
   faq=[("What is an SEO audit?","An SEO audit evaluates website performance and optimization opportunities."),
        ("Why are SEO audits important?","They identify issues impacting search visibility."),
        ("What areas are reviewed?","Technical SEO, content, backlinks, keywords, and user experience."),
        ("How often should audits be conducted?","Every 3–6 months."),
        ("Can audits improve rankings?","Yes. Fixing issues can enhance search performance."),
        ("What tools are used in SEO audits?","Analytics, crawling, keyword, and technical SEO tools."),
        ("Who needs an SEO audit?","Any business seeking better search visibility.")],
   related=[("technical-seo.html","gauge","Technical SEO","Fix the issues"),("seo.html","search","SEO Services","Ongoing growth"),("ai-seo.html","sparkles","AI SEO","AI Overviews")],
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
   faq=[("What is guest posting?","Publishing content on third-party websites."),
        ("Why is guest posting valuable?","It builds authority and backlinks."),
        ("Does guest posting improve SEO?","Yes, when done on reputable websites."),
        ("What industries use guest posting?","Technology, healthcare, finance, education, and more."),
        ("How are guest post sites selected?","Based on authority, relevance, and audience."),
        ("Can guest posting increase traffic?","Yes. It exposes brands to new audiences."),
        ("Is guest posting still effective?","Yes, when quality standards are maintained.")],
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
   faq=[("What are Content Writing Services?","Content Writing Services involve creating high-quality, engaging, and SEO-friendly content for websites, blogs, landing pages, product descriptions, articles, and marketing campaigns to attract, inform, and convert potential customers."),
        ("Why are professional Content Writing Services important for businesses?","Professional content helps improve search engine rankings, build brand authority, increase website engagement, generate qualified leads, and communicate your business message effectively to your target audience."),
        ("How does SEO content writing improve search rankings?","SEO content writing incorporates relevant keywords, search intent, content structure, internal linking, and user-focused information to help websites rank higher in search engine results and attract organic traffic."),
        ("What types of content do Content Writing Services include?","Content Writing Services typically include website content, service pages, blog articles, landing pages, product descriptions, press releases, case studies, email content, social media content, and SEO-focused articles."),
        ("Can Content Writing Services help generate leads and sales?","Yes. Well-written content educates visitors, answers their questions, builds trust, and guides them through the buying process, increasing conversions, leads, and sales opportunities."),
        ("How often should businesses publish new content?","Businesses should publish content consistently based on their industry and marketing goals. Regular content updates help improve SEO performance, audience engagement, and online visibility."),
        ("What makes Evision Infoserve's Content Writing Services different?","Evision Infoserve combines SEO expertise, audience research, AI-search optimization, industry knowledge, and conversion-focused writing to create content that drives traffic, engagement, rankings, and business growth.")],
   related=[("content-marketing.html","pen-tool","Content Marketing","Full strategy"),("guest-posting.html","newspaper","Guest Posting","Off-site content"),("seo.html","search","SEO Services","Make it rank")],
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
   faq=[("What is Digital PR?","Digital PR builds online visibility through media coverage and brand mentions."),
        ("How does Digital PR support SEO?","It generates authoritative backlinks and mentions."),
        ("What are Digital PR campaigns?","Strategies designed to earn media attention and coverage."),
        ("Can Digital PR improve brand authority?","Yes. Media exposure strengthens credibility."),
        ("Which businesses need Digital PR?","Startups, enterprises, ecommerce brands, and service providers."),
        ("How are Digital PR results measured?","Coverage, backlinks, mentions, and referral traffic."),
        ("Is Digital PR different from traditional PR?","Yes. It focuses primarily on online channels.")],
   related=[("link-building.html","link","Link Building","Authority links"),("guest-posting.html","newspaper","Guest Posting","Placed articles"),("orm.html","shield-check","ORM","Reputation")],
   side_title="Free digital PR ideas", side_text="Get a couple of campaign angles tailored to your brand.",
   cta_h="Earn the press coverage that builds authority"),

 "industry-seo": dict(
   title="Industry-Based SEO Services", name="Industry-Based SEO", eyebrow="SEO · Industry",
   metadesc="Industry-based SEO from Evision Infoserve — customised SEO strategies for healthcare, education, travel, ecommerce, finance and more.",
   lead="Customised SEO strategies built around the keywords, buyers and competition of your specific industry.",
   qa_q="What is industry-based SEO?", qa_a="Industry-based SEO is a customised SEO strategy designed around the unique keywords, audience behaviour, regulations and competition of a specific industry — so healthcare, education, travel, ecommerce, finance and other sectors each get an approach that fits how their buyers actually search.",
   overview_h="SEO tuned to how your industry searches",
   overview1="Different industries have different keywords, customer journeys, regulations and competitive landscapes. A generic SEO playbook leaves rankings and qualified leads on the table.",
   overview2="We build SEO around your sector — mapping the searches your buyers really make, the trust signals your market expects, and the conversion paths that turn visits into enquiries.",
   included=[("stethoscope","Healthcare SEO","Visibility and patient acquisition for clinics & providers."),
             ("graduation-cap","Education SEO","Rankings for schools, colleges, institutes and edtech."),
             ("plane","Travel SEO","Search visibility for agencies, hotels and tour operators."),
             ("shopping-cart","Ecommerce SEO","Product, category and transactional-keyword strategies."),
             ("landmark","Finance & legal SEO","Compliant, authority-led SEO for regulated sectors."),
             ("search","Sector keyword research","The terms and intent unique to your market.")],
   process=G_PROCESS("We research your industry's keywords, buyers and competitors.",
                     "A sector-specific strategy, content and trust-signal plan.",
                     "We optimise pages, content and technical foundations.",
                     "Industry-benchmarked ranking and lead reporting."),
   deliverables=["An industry keyword & competitor map","A sector-tailored SEO strategy","Optimised industry landing pages","Trust & compliance-aware content","A monthly ranking + lead report"],
   faq=[("What are Industry-Based SEO Services?","Industry-Based SEO Services are customized SEO strategies designed specifically for the unique requirements, audience behavior, and search trends of different industries."),
        ("Why is industry-specific SEO important?","Different industries have different keywords, customer journeys, regulations, and competitive landscapes that require specialized optimization approaches."),
        ("Do you provide Healthcare SEO Services?","Yes. Healthcare SEO helps hospitals, clinics, healthcare providers, and medical practices improve online visibility and patient acquisition."),
        ("How does Education SEO help educational institutions?","Education SEO improves rankings for schools, colleges, universities, training institutes, and edtech platforms to attract students and inquiries."),
        ("What is Travel SEO?","Travel SEO helps travel agencies, tour operators, hotels, and tourism businesses increase visibility for travel-related searches and bookings."),
        ("Can Ecommerce businesses benefit from Industry-Based SEO?","Yes. Ecommerce SEO focuses on product visibility, category optimization, transactional keywords, and conversion-driven search strategies."),
        ("Which industries can benefit from specialized SEO services?","Healthcare, education, travel, finance, real estate, manufacturing, technology, legal services, ecommerce, and professional services can all benefit from industry-specific SEO.")],
   related=[("seo.html","search","SEO Services","The full programme"),("local-seo.html","map-pin","Local SEO","Location-based"),("ecommerce-seo.html","shopping-cart","Ecommerce SEO","Online stores")],
   side_title="Free industry SEO review", side_text="See the sector-specific opportunities your competitors are winning.",
   cta_h="Win the searches that matter in your industry"),

 "affiliate-marketing": dict(
   title="Affiliate Marketing Services", name="Affiliate Marketing", eyebrow="Marketing · Performance",
   metadesc="Affiliate marketing from Evision Infoserve — performance-based programs that drive qualified traffic, leads and sales through trusted partners.",
   lead="Performance-based programs that drive qualified traffic, leads and sales — you pay for results, not promises.",
   qa_q="What is affiliate marketing?", qa_a="Affiliate marketing is a performance-based strategy where partners (affiliates) promote your products or services and earn a commission for each lead, sale or conversion they generate — a cost-effective, results-driven way to expand reach.",
   overview_h="Pay for performance, not for clicks",
   overview1="Affiliate marketing turns a network of trusted publishers, creators and partners into a commission-based sales channel. You pay when they deliver a lead, sale or conversion — not before.",
   overview2="We design, launch and manage affiliate programs end-to-end — recruiting the right partners, setting fair commission models, and tracking every action so growth stays profitable.",
   included=[("users","Partner recruitment","Find and onboard relevant, high-quality affiliates."),
             ("percent","Commission models","PPS, PPL, PPC and recurring structures that work."),
             ("link","Tracking & attribution","Accurate tracking of every click, lead and sale."),
             ("shield-check","Fraud & quality control","Protect your program from low-quality traffic."),
             ("file-text","Creatives & assets","Banners, links and copy that affiliates convert with."),
             ("bar-chart-3","Performance reporting","See ROI, top partners and program health.")],
   process=G_PROCESS("We audit your offer, margins and ideal partner profile.",
                     "We set up tracking, commissions and program assets.",
                     "We recruit, activate and manage your affiliates.",
                     "Monthly reporting optimises partners and payouts."),
   deliverables=["An affiliate program strategy","Tracking & attribution setup","A recruited partner network","Creative assets for affiliates","A monthly performance & ROI report"],
   faq=[("What is Affiliate Marketing?","Affiliate Marketing is a performance-based marketing strategy where affiliates promote products or services and earn commissions for generating leads, sales, or conversions."),
        ("How does Affiliate Marketing work?","Affiliates use websites, blogs, social media, email marketing, or other channels to promote products and earn commissions when specific actions are completed."),
        ("What are the benefits of Affiliate Marketing?","Affiliate Marketing increases brand exposure, drives qualified traffic, generates sales, and offers a cost-effective customer acquisition model."),
        ("What are the common Affiliate Marketing compensation models?","Popular models include Pay Per Sale (PPS), Pay Per Lead (PPL), Pay Per Click (PPC), and recurring commission structures."),
        ("Which businesses benefit from Affiliate Marketing?","Ecommerce stores, SaaS companies, educational platforms, financial services, and subscription-based businesses commonly use affiliate marketing."),
        ("Can Affiliate Marketing improve online sales?","Yes. A well-managed affiliate program can expand market reach and drive consistent sales through trusted partners."),
        ("Is Affiliate Marketing suitable for small businesses?","Yes. Affiliate marketing provides scalable growth opportunities with performance-based costs.")],
   related=[("ppc.html","target","PPC & Paid Ads","Paid scale"),("content-marketing.html","pen-tool","Content Marketing","Partner content"),("ai-marketing.html","sparkles","AI Digital Marketing","Automation")],
   side_title="Free affiliate program review", side_text="See whether a performance channel fits your margins and goals.",
   cta_h="Grow sales with a pay-for-performance channel"),

 "youtube-marketing": dict(
   title="YouTube Video Marketing Services", name="YouTube Video Marketing", eyebrow="Marketing · Video",
   metadesc="YouTube marketing from Evision Infoserve — channel management, YouTube SEO and video strategy that grow visibility, subscribers and leads.",
   lead="Channel management, YouTube SEO and video strategy that grow visibility, subscribers and leads.",
   qa_q="What is YouTube marketing?", qa_a="YouTube marketing helps businesses increase video visibility, grow subscribers, improve engagement and generate leads through strategic content, channel management and YouTube SEO.",
   overview_h="Turn video into a discovery channel",
   overview1="YouTube is the world's second-largest search engine. Done right, it builds brand awareness, educates buyers and feeds leads — and the videos keep working long after you publish.",
   overview2="We plan, optimise and manage your channel: from content strategy and YouTube SEO to thumbnails, publishing and growth — all measured against real business goals.",
   included=[("youtube","Channel management","Planning, publishing, branding and growth."),
             ("search","YouTube SEO","Titles, tags, descriptions and thumbnails that rank."),
             ("clapperboard","Video content strategy","Topics and formats your audience actually watches."),
             ("image","Thumbnails & branding","Click-worthy, consistent channel branding."),
             ("users","Audience growth","Subscriber and engagement growth strategies."),
             ("bar-chart-3","Performance analytics","Watch-time, retention and lead tracking.")],
   process=G_PROCESS("We audit your channel, niche and competitors.",
                     "A content, SEO and growth strategy is built.",
                     "We optimise, publish and manage your channel.",
                     "Monthly analytics guide the next content batch."),
   deliverables=["A channel & competitor audit","A video content strategy","YouTube-SEO optimised uploads","Branded thumbnails & assets","A monthly growth & engagement report"],
   faq=[("What are YouTube Marketing Services?","YouTube Marketing Services help businesses increase video visibility, grow subscribers, improve engagement, and generate leads through strategic video marketing."),
        ("What is YouTube Channel Management?","YouTube Channel Management includes content planning, publishing, optimization, branding, performance monitoring, and audience growth strategies."),
        ("How does YouTube SEO improve video rankings?","YouTube SEO optimizes titles, descriptions, keywords, tags, thumbnails, and engagement signals to improve discoverability and rankings."),
        ("Why is YouTube important for businesses?","YouTube helps businesses build brand awareness, educate audiences, generate leads, and improve online visibility through video content."),
        ("What types of businesses benefit from YouTube Marketing?","Educational institutions, ecommerce brands, healthcare providers, consultants, SaaS companies, and service businesses benefit from YouTube marketing."),
        ("Can YouTube Marketing generate leads?","Yes. Strategic video content can attract qualified viewers and guide them toward inquiries, purchases, or conversions."),
        ("How long does YouTube growth take?","Growth depends on content quality, consistency, optimization, audience engagement, and competition within the niche.")],
   related=[("social-media.html","thumbs-up","Social Media","Distribute video"),("content-marketing.html","pen-tool","Content Marketing","Repurpose content"),("seo.html","search","SEO Services","Rank everywhere")],
   side_title="Free YouTube channel review", side_text="Find the quick wins holding back your video visibility.",
   cta_h="Grow your brand on the world's #2 search engine"),

 "email-marketing": dict(
   title="Email Marketing Services", name="Email Marketing", eyebrow="Marketing · Lifecycle",
   metadesc="Email marketing from Evision Infoserve — targeted campaigns, automation and lead nurturing that drive engagement, conversions and repeat sales.",
   lead="Targeted campaigns, automation and lead nurturing that drive engagement, conversions and repeat sales.",
   qa_q="What are email marketing services?", qa_a="Email marketing services help businesses communicate with customers through targeted email campaigns — promotions, newsletters, welcome and nurturing sequences — designed to increase engagement, leads and sales with measurable ROI.",
   overview_h="The channel you actually own",
   overview1="Unlike rented social audiences, your email list is an asset you own. Done well, email delivers some of the highest ROI in marketing through timely, relevant, personalised messages.",
   overview2="We plan and run your campaigns and automations — from welcome and nurture sequences to promotions and retention — and measure every open, click and conversion.",
   included=[("mail","Campaign management","Promotions, newsletters and announcements."),
             ("workflow","Automation & flows","Welcome, nurture, cart and retention sequences."),
             ("users","List growth & segmentation","Grow and segment your audience for relevance."),
             ("pen-tool","Copy & design","On-brand emails built to be opened and clicked."),
             ("target","Lead nurturing","Guide prospects along the buying journey."),
             ("bar-chart-3","Performance reporting","Open, click, conversion and ROI tracking.")],
   process=G_PROCESS("We audit your list, tools and current performance.",
                     "We plan campaigns, automations and segments.",
                     "We build, send and optimise your emails.",
                     "Monthly reporting improves every metric."),
   deliverables=["An email strategy & calendar","Automated lifecycle flows","Designed, written campaigns","Segmented, growing lists","A monthly performance & ROI report"],
   faq=[("What are Email Marketing Services?","Email Marketing Services help businesses communicate with customers through targeted email campaigns designed to increase engagement, leads, and sales."),
        ("What types of emails are included in Email Marketing?","Services include promotional emails, newsletters, welcome emails, lead nurturing campaigns, transactional emails, and customer retention campaigns."),
        ("Why is Email Marketing effective?","Email marketing provides direct communication with customers, high ROI, personalized messaging, and measurable campaign performance."),
        ("Can Email Marketing generate leads and sales?","Yes. Email campaigns nurture prospects, encourage repeat purchases, and drive conversions through targeted communication."),
        ("What is Lead Nurturing Email Marketing?","Lead nurturing emails guide potential customers through the buying journey by providing relevant information and personalized offers."),
        ("How often should businesses send marketing emails?","Frequency depends on audience preferences, business goals, and content quality, but consistency is essential."),
        ("How is Email Marketing performance measured?","Key metrics include open rates, click-through rates, conversions, subscriber growth, and return on investment.")],
   related=[("ai-marketing.html","sparkles","AI Digital Marketing","Automation"),("content-marketing.html","pen-tool","Content Marketing","Content to send"),("affiliate-marketing.html","percent","Affiliate Marketing","Partner reach")],
   side_title="Free email marketing review", side_text="See where your campaigns and automations are leaking revenue.",
   cta_h="Turn your email list into reliable revenue"),

 "mobile-app-marketing": dict(
   title="Mobile App Marketing Services", name="Mobile App Marketing", eyebrow="Marketing · App Growth",
   metadesc="Mobile app marketing from Evision Infoserve — App Store Optimization (ASO), app CRO and growth campaigns that drive downloads, engagement and retention.",
   lead="App Store Optimization, app CRO and growth campaigns that drive downloads, engagement and retention.",
   qa_q="What is mobile app marketing?", qa_a="Mobile app marketing helps increase an app's visibility, downloads, engagement and retention — combining App Store Optimization (ASO), conversion-rate optimisation and growth campaigns across app stores and beyond.",
   overview_h="More downloads, better retention",
   overview1="Getting an app built is only half the battle — being found and kept is the rest. Most app growth hides in store visibility and the conversion of a listing into an install.",
   overview2="We optimise your app store presence (ASO), improve install conversion (App CRO), and run growth campaigns that acquire the right users and keep them engaged.",
   included=[("smartphone","App Store Optimization","Keyword, metadata and listing optimisation."),
             ("mouse-pointer-click","App CRO","Better screenshots, copy and pages that convert."),
             ("download","User acquisition","Campaigns that bring in the right installs."),
             ("repeat","Retention & engagement","Keep users active beyond the first open."),
             ("search","ASO keyword research","Rank for the terms users search in stores."),
             ("bar-chart-3","Analytics & reporting","Installs, retention and revenue tracking.")],
   process=G_PROCESS("We audit your store listings, keywords and funnel.",
                     "An ASO, CRO and acquisition plan is built.",
                     "We optimise listings and run growth campaigns.",
                     "Monthly reporting tunes installs and retention."),
   deliverables=["An ASO & store-listing audit","Optimised app store pages","An acquisition campaign plan","Retention & engagement tactics","A monthly install & retention report"],
   faq=[("What are Mobile App Marketing Services?","Mobile App Marketing Services help increase app visibility, downloads, user engagement, and retention through strategic marketing campaigns."),
        ("What is App Store Optimization (ASO)?","ASO improves app discoverability in app stores through keyword optimization, metadata enhancements, and conversion-focused app listings."),
        ("What is App Conversion Rate Optimization (App CRO)?","App CRO improves install rates and user engagement by optimizing app store pages, screenshots, descriptions, and user journeys."),
        ("Why is Mobile App Marketing important?","Effective app marketing helps businesses acquire users, improve retention, and maximize revenue from mobile applications."),
        ("How does ASO improve app downloads?","ASO increases visibility in app store search results, helping more users discover and install the application."),
        ("Can Mobile App Marketing reduce acquisition costs?","Yes. Organic app visibility through ASO can lower paid advertising expenses and improve long-term growth."),
        ("Which businesses need Mobile App Marketing?","Startups, ecommerce brands, SaaS companies, gaming apps, healthcare apps, educational apps, and enterprise applications benefit from app marketing.")],
   related=[("ppc.html","target","PPC & Paid Ads","Paid installs"),("seo.html","search","SEO Services","Web visibility"),("ai-marketing.html","sparkles","AI Digital Marketing","Automation")],
   side_title="Free ASO audit", side_text="See how discoverable your app is — and how to lift installs.",
   cta_h="Get more of the right users installing your app"),
}


# ── Simple pages (utility + legal) ──
def simple_page(slug, c):
    body = c["body"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow"><!-- DEV PHASE: remove before launch -->
<title>{esc(c['title'])} | Evision Infoserve</title>
<meta name="description" content="{esc(c['metadesc'])}">
<link rel="stylesheet" href="/assets/tokens.css{VER}">
<link rel="stylesheet" href="/assets/site.css{VER}">
<link rel="stylesheet" href="/assets/chrome.css{VER}">
<link rel="stylesheet" href="/assets/service.css">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
</head>
<body data-page="{c.get('page','')}">

<section class="svc-hero">
  <div class="container svc-hero-inner">
    <nav class="crumb"><a href="/index.html">Home</a><span class="sep">/</span><span style="color:var(--color-gold-500)">{esc(c['name'])}</span></nav>
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
    <a href="/contact.html" data-audit-open class="btn btn-primary btn-lg">Get a Free Audit</a>
  </div>
</section>

<script src="/assets/site.js{VER}"></script>
<script src="/assets/chrome.js{VER}"></script>
<script src="/assets/pricing.js{VER}"></script>
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
    <p style="margin-top:24px">Want the full case study for your industry? <a href="/contact.html" data-audit-open>Ask us for relevant examples</a> and we'll share detailed results.</p>"""),

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
    <p style="margin-top:24px">Curious whether we've worked in your niche? <a href="/contact.html" data-audit-open>Get in touch</a> — we'll share relevant results.</p>"""),

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
    <p style="margin-top:24px">Don't see your role? We still want to hear from great people. Email your CV to <a href="mailto:info@evisioninfoserve.com">info@evisioninfoserve.com</a> or <a href="/contact.html" data-audit-open>say hello</a>.</p>"""),

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
    <p style="margin-top:24px">Want references in your industry? <a href="/contact.html" data-audit-open>Ask us</a> — we're happy to connect you with relevant clients.</p>"""),

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
