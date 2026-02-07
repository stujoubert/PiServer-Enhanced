PRAGMA foreign_keys=ON;
BEGIN TRANSACTION;

-- -------------------------------------------------------------------
-- Seed accounts: default admin user
-- IMPORTANT: Replace password_hash with one generated on install if desired
-- -------------------------------------------------------------------
INSERT OR IGNORE INTO accounts (id, username, password_hash, role, active)
VALUES (
  1,
  'admin',
  'scrypt:32768:8:1$g9Gkat5xiHHwgAn5$74129dbb5590079299c2ddffd46021895ced0443b981162d7fba2ca8aa9765ded2deda5d5a2accab15461b8818e35bf72633a25aad398e85f53d247febe712df',
  'admin',
  1
);

-- -------------------------------------------------------------------
-- Seed settings (optional, keep only what your app expects)
-- -------------------------------------------------------------------
INSERT OR IGNORE INTO settings (key, value) VALUES ('week_type', 'mon_fri');

COMMIT;
