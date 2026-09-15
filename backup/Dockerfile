FROM postgres:16
COPY backup/backup-once.sh backup/backup-loop.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup-once.sh /usr/local/bin/backup-loop.sh
ENTRYPOINT ["/usr/local/bin/backup-loop.sh"]
