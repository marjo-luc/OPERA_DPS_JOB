# Use miniconda as the base image with the specified version.
FROM continuumio/miniconda3:23.10.0-1
ENV LANG en_US.UTF-8
ENV TZ US/Pacific
ARG DEBIAN_FRONTEND=noninteractive

# Copy the environment.yml file into the container
COPY ./env.yml /tmp/env.yml

# Update Conda and create a new environment based on the environment.yml file
RUN conda env update --quiet --solver libmamba -n watermask -f /tmp/env.yml && \
    conda clean --all

RUN mkdir -p OPERA_DPS_JOB

COPY ./run.sh OPERA_DPS_JOB/run.sh
COPY ./water_mask_to_cog.py OPERA_DPS_JOB/water_mask_to_cog.py

RUN chmod +x OPERA_DPS_JOB/run.sh && chmod +x OPERA_DPS_JOB/water_mask_to_cog.py

