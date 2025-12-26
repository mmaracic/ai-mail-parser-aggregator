// Create admin user with password
CREATE USER admin IDENTIFIED BY 'admin_password';
GRANT ALL PRIVILEGES TO admin;

// Optional: Create additional users with different roles
// CREATE USER readonly IDENTIFIED BY 'readonly_password';
// GRANT READ TO readonly;
