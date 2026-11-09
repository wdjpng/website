# These generated archives contain only the bundled theme demonstrations.
# Keep them crawlable so search engines can see noindex.
module PersonalSiteSEO
  class DemoArchives < Jekyll::Generator
    safe true
    priority :lowest

    def generate(site)
      site.pages.each do |page|
        next unless page.url.start_with?("/blog/", "/news/", "/projects/")

        page.data["noindex"] = true
        page.data["sitemap"] = false
      end
    end
  end
end
