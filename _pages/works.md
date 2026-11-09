---
layout: page
permalink: /works/
title: works
years: [2026, 2025, 2024, 2023, 2021, 2020]
nav: true
nav_order: 1
seo_title: "Research & Projects | Lukas Münzel"
description: "Research, mathematical writing and software projects by Lukas Münzel, including randomized linear algebra, KL divergence estimation and the Lorien app."
---
<!-- _pages/publications.md -->
<div class="publications">

{%- for y in page.years %}
  <h2 class="year">{{y}}</h2>
  {% bibliography -f papers -q @*[year={{y}}]* %}
{% endfor %}

</div>
