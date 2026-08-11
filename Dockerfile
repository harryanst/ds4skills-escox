FROM konstantinospetrakis/esco-skill-extractor
CMD ["python", "-m", "esco_skill_extractor", "--host", "0.0.0.0", "--port", "10000"]
