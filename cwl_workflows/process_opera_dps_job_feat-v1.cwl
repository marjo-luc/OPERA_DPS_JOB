cwlVersion: v1.2
$graph:
- class: Workflow
  label: operawatermask1
  doc: None
  id: operawatermask1
  inputs: {}
  outputs:
    out:
      type: Directory
      outputSource: process/outputs_result
  steps:
    process:
      run: '#main'
      in: {}
      out:
      - outputs_result
- class: CommandLineTool
  id: main
  requirements:
    DockerRequirement:
      dockerPull: ghcr.io/marjo-luc/opera_dps_job:feat-v1
    NetworkAccess:
      networkAccess: true
    ResourceRequirement:
      ramMin: 5
      coresMin: 1
      outdirMax: 20
  baseCommand: /OPERA_DPS_JOB/run.sh
  inputs: {}
  outputs:
    outputs_result:
      outputBinding:
        glob: ./output*
      type: Directory
s:author:
- class: s:Person
  s:name: None
s:contributor:
- class: s:Person
  s:name: None
s:citation: null
s:codeRepository: https://github.com/marjo-luc/OPERA_DPS_JOB.git
s:commitHash: 880fdc129a78a46138730f605b3a9ce5fcf248d4
s:dateCreated: 2025-11-18
s:license: https://github.com/marjo-luc/OPERA_DPS_JOB/blob/feat-v1/LICENSE
s:softwareVersion: 1.0.0
s:version: 0.1.1
s:releaseNotes: None
s:keywords: null
$namespaces:
  s: https://schema.org/
$schemas:
- https://raw.githubusercontent.com/schemaorg/schemaorg/refs/heads/main/data/releases/9.0/schemaorg-current-http.rdf
