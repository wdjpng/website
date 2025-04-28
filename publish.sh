sudo bundle install
sudo bundle exec jekyll build
rsync -avz _site/* lukas:/var/www/html/