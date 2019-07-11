# odoo server config for %(url)s
upstream odoo {
        server 127.0.0.1:%(port)s;
}
upstream odoochat {
        server 127.0.0.1:%(longpollingport)s;
}


server {
        listen 80;
        server_name %(url)s;
        proxy_read_timeout 720s;
        proxy_connect_timeout 720s;
        proxy_send_timeout 720s;

        # Add Headers for odoo proxy mode
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;

        # Redirect longpoll requests to odoo longpolling port
        location /longpolling {
                proxy_pass http://odoochat;
        }

        # Redirect requests to odoo backend server
        location / {
          proxy_redirect off;
          proxy_pass http://odoo;
        }

        # common gzip
        gzip_types text/css text/less text/plain text/xml application/xml application/json application/javascript;
        gzip on;
}
