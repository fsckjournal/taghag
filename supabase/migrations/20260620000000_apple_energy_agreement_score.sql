-- Direction-agreement score between MIK's manual energy cues and Apple's
-- automatic pace curve, mirroring bpm_agreement_score (Rekordbox-vs-Apple).

alter table public.apple_derived_features
  add column if not exists energy_agreement_score numeric;
