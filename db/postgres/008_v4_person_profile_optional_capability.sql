BEGIN;

ALTER TABLE v4_person_profile.person_profile_snapshots
    DROP CONSTRAINT person_profile_snapshots_capability_domains_check;
ALTER TABLE v4_person_profile.person_profile_snapshots
    ADD CONSTRAINT person_profile_snapshots_capability_domains_check
    CHECK (jsonb_typeof(capability_domains) = 'array');

ALTER TABLE v4_person_profile.person_profile_catalog
    DROP CONSTRAINT person_profile_catalog_capability_domains_check;
ALTER TABLE v4_person_profile.person_profile_catalog
    ADD CONSTRAINT person_profile_catalog_capability_domains_check
    CHECK (jsonb_typeof(capability_domains) = 'array');

COMMIT;
