# Personal website SEO — munzel.com is primary

Updated October 31, 2026 (Pacific time).

Canonical origin: https://munzel.com. All canonical links, sitemap entries,
Open Graph URLs, structured-data identifiers, and public internal links use
this origin. The homepage connects Lukas Münzel, Lukas Muenzel and Lukas
Munzel to the same Person. Site alternate names include munzel.com.

The personal website at lukasmuenzel.com and www.lukasmuenzel.com permanently
redirects to the corresponding munzel.com path, preserving queries.
www.munzel.com also redirects to the non-www origin. Existing protected
locations on the original hostname retain their authentication. Qwen retains
its munzel.com location, isolation headers and disabled API.

munzel.com.nginx and www.lukasmuenzel.com.nginx contain the deployed host
configurations. The shared default nginx file also changes only the public
lukasmuenzel.com TLS location and that hostname's HTTP redirect to the new
origin; unrelated service hosts are unchanged. Keep the redirects at least
a year, ideally indefinitely. Keep both domains and their certificates valid.

Metadata comes from _includes/metadata.html and _config.yml. Original article
pages show a linked author byline. The portrait has explicit dimensions and
high loading priority. _data/preview_images.json maps publication originals
to small WebP previews and dimensions; animations retain their original file.
Regenerate preview files and this map if replacing the originals. New unmapped
previews fall back to their source file. All previews load lazily. Stable PNG
favicons are in assets/img. Nginx compresses CSS, JavaScript and XML responses.

Theme examples have noindex: true and sitemap: false. _plugins/seo_indexing.rb
also excludes generated /blog/, /news/ and /projects/ archives. Narrow this rule
before publishing real content in those archives. Keep demo pages crawlable
so search engines can read noindex. Existing privacy crawl exclusions remain.

Build with a UTF-8 locale and the repository Ruby version:
LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 rbenv exec bundle exec jekyll build

Google Search Console still requires the user's authenticated session:
verify both properties, submit the change of address from lukasmuenzel.com to
munzel.com, submit https://munzel.com/sitemap.xml, and request homepage indexing.
Do not migrate unrelated service subdomains. Update external public profile
website links to munzel.com when their owner is ready.

Browsers that cached the short-lived reverse redirect from the earlier pass
may need a hard refresh or cached-site-data clearance. The final live HTTP
checks show munzel.com returning 200 and the old public site returning 301.

Production backup: /home/alwyzon/backup/seo-munzel-primary-20261031/
This task's work/munzel-primary directory retains the original configuration,
staged routing test, deployment scripts and live verification results.
