#FROM konstantinospetrakis/esco-skill-extractor
#CMD ["python", "-m", "esco_skill_extractor", "--host", "0.0.0.0", "--port", "10000"]


FROM konstantinospetrakis/esco-skill-extractor
COPY scored_server.py /scored_server.py
CMD ["python", "/scored_server.py"]
