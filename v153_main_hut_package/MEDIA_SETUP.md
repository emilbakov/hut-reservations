# Public hut photo serving

v153 sets public photo URLs to /media/ and uses /var/www/hut-media by default in production. Setting MEDIA_ROOT alone does not configure nginx.

The deployment step:

1. Creates the media directory if absent, owned by the deploy account and readable by nginx.
2. Copies files referenced by Hut.image from the old project root or project/media tree. Original files stay in place. Conflicting/missing originals or unsafe paths stop the helper without overwriting any photo. An interrupted copy can be retried.
3. Generates v153_main_hut_package/nginx_media_generated.conf for the selected MEDIA_ROOT.

If Gunicorn runs as a different user, give that service user write access to the media directory. Existing directories are not recursively chowned or chmodded. Deployment stops if the deploy account cannot write there.

## Configure nginx once

If the site already has a /media/ location, verify that its alias matches the generated file. Update that location instead of adding a duplicate.

Install the generated example as a root-owned snippet:

```bash
cd /home/deploy/hut-reservations
sudo install -d -m 755 /etc/nginx/snippets
sudo install -m 644 -o root -g root v153_main_hut_package/nginx_media_generated.conf /etc/nginx/snippets/summitdesk-media-v153.conf
```

In the existing nginx server block that proxies this site to Gunicorn, add:

```nginx
include /etc/nginx/snippets/summitdesk-media-v153.conf;
```

Use your actual site configuration file. The package cannot identify it from the source snapshot and does not modify it automatically. Apply the mapping in the application-serving HTTPS block if HTTP only redirects to HTTPS.

For the default directory, the generated contents are:

```nginx
location ^~ /media/ {
    alias /var/www/hut-media/;
    autoindex off;
    add_header X-Content-Type-Options nosniff always;
    limit_except GET HEAD { deny all; }
}
```

Validate before reloading:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

If validation fails, correct or revert the nginx edit and do not reload. Open an existing hut photo URL to verify the mapping. Retain any backup of the nginx configuration made before your edit. Source rollback does not modify nginx or remove photo files.

## Inspect copy work without changing photos

After loading the same virtualenv and production environment as deploy_v153.sh:

```bash
python v153_main_hut_package/prepare_media_v153.py --dry-run
```

The helper handles existing local public hut photos under huts/. External storage, custom image paths and custom old media roots require a separate migration; it refuses missing or unsafe paths rather than guessing. No production photo migration was executed while creating this ZIP.

References: [Django media serving](https://docs.djangoproject.com/en/6.1/howto/static-files/) and [nginx alias](https://nginx.org/en/docs/http/ngx_http_core_module.html#alias).
