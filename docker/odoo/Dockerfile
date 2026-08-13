FROM odoo:16

USER root
RUN pip3 install --no-cache-dir watchdog
COPY docker/watcher /opt/odoo-dev/watchers
COPY docker/odoo/entrypoint-dev.sh /opt/odoo-dev/entrypoint-dev.sh
RUN chmod +x /opt/odoo-dev/entrypoint-dev.sh
USER odoo
