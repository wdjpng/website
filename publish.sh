#!/bin/bash
bundle config set --local path 'vendor/bundle'
bundle install
bundle exec jekyll build
rsync -avz _site/* lukas:/var/www/html/