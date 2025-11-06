# #!/usr/bin/env bash

# Break build on error
set -e

# Distribute the content pages
python parse_content.py "$WEBSITE"
# Copy default base pages
cp --no-clobber content/pages/defaults/404.md "$WEBSITE/content/pages/404.md"
cp --no-clobber content/pages/defaults/colofon.md "$WEBSITE/content/pages/colofon.md"
cp --no-clobber content/pages/defaults/home.md "$WEBSITE/content/pages/home.md"

# Copy bibliography files
cp content/bibitems_umcg-anes.json "$WEBSITE/content/bibitems_umcg-anes.json"
cp content/authorkeys_umcg-anes.json "$WEBSITE/content/authorkeys_umcg-anes.json"
cp content/groupkeys_umcg-anes.json "$WEBSITE/content/groupkeys_umcg-anes.json"

# Copy images when deploying locally (for development)
# Do not overwrite existing images to save time
if [ "$LOCAL" = "1" ]; then
  if [ -d "$WEBSITE/output/images" ]; then
    mv "$WEBSITE/output/images" "$WEBSITE/temp_dir"
    rm -rf "$WEBSITE/output/"
    mkdir "$WEBSITE/output"
    mv "$WEBSITE/temp_dir" "$WEBSITE/output/images"
    rm -rf "$WEBSITE/temp_dir"
  fi
  cp -r --no-clobber assets/images/. "$WEBSITE/output/images"
  cp -r --no-clobber content/images/. "$WEBSITE/output/images"
fi
