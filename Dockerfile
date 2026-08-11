#FROM konstantinospetrakis/esco-skill-extractor
#CMD ["python", "-m", "esco_skill_extractor", "--host", "0.0.0.0", "--port", "10000"]

FROM konstantinospetrakis/esco-skill-extractor@sha256:8836285486dfb94de5c541e2ab9bd19d563df3fb7c6036020179d191c9fc42ff
COPY scored_server.py /scored_server.py
CMD ["python", "/scored_server.py"]
