USE aiims_connect;
CREATE ROLE IF NOT EXISTS 'aiims_app_ro';
CREATE ROLE IF NOT EXISTS 'aiims_app_rw';
GRANT SELECT ON aiims_connect.* TO 'aiims_app_ro';
GRANT SELECT,INSERT,UPDATE,DELETE,EXECUTE ON aiims_connect.* TO 'aiims_app_rw';
-- Run these role assignments as an administrator if desired:
-- GRANT 'aiims_app_rw' TO 'aiims_app'@'localhost';
-- SET DEFAULT ROLE 'aiims_app_rw' TO 'aiims_app'@'localhost';
