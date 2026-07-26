"""Platform engines. Each engine is independent logic; the API layer mounts one
router per engine so the platform ships as a single deployable service.

  delay_prediction -> ../ml (the built, validated module)
  scheduler        -> OR-Tools CP-SAT resource assignment
  validator        -> construction-sequencing rules engine
"""
