
-- Database Meta Table
CREATE TABLE IF NOT EXISTS client_databases (
    id int(10) unsigned NOT NULL auto_increment,
    name varchar(64) NOT NULL,
    owner varchar(64) NOT NULL,
    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY name (name)
);

-- ProFTP Tables
CREATE TABLE IF NOT EXISTS ftpgroup (
    groupname varchar(16) NOT NULL default '',
    gid smallint(6) NOT NULL default '5500',
    members varchar(16) NOT NULL default '',
    KEY groupname (groupname)
);

CREATE TABLE IF NOT EXISTS ftpquotalimits (
    name varchar(30) default NULL,
    quota_type enum('user','group','class','all') NOT NULL default 'user',
    per_session enum('false','true') NOT NULL default 'false',
    limit_type enum('soft','hard') NOT NULL default 'soft',
    bytes_in_avail bigint(20) unsigned NOT NULL default '0',
    bytes_out_avail bigint(20) unsigned NOT NULL default '0',
    bytes_xfer_avail bigint(20) unsigned NOT NULL default '0',
    files_in_avail int(10) unsigned NOT NULL default '0',
    files_out_avail int(10) unsigned NOT NULL default '0',
    files_xfer_avail int(10) unsigned NOT NULL default '0'
);

CREATE TABLE IF NOT EXISTS ftpquotatallies (
    name varchar(30) NOT NULL default '',
    quota_type enum('user','group','class','all') NOT NULL default 'user',
    bytes_in_used bigint(20) unsigned NOT NULL default '0',
    bytes_out_used bigint(20) unsigned NOT NULL default '0',
    bytes_xfer_used bigint(20) unsigned NOT NULL default '0',
    files_in_used int(10) unsigned NOT NULL default '0',
    files_out_used int(10) unsigned NOT NULL default '0',
    files_xfer_used int(10) unsigned NOT NULL default '0'
);

CREATE TABLE IF NOT EXISTS ftpuser (
    id int(10) unsigned NOT NULL auto_increment,
    userid varchar(32) NOT NULL default '',
    passwd varchar(32) NOT NULL default '',
    uid smallint(6) NOT NULL default '5500',
    gid smallint(6) NOT NULL default '5500',
    homedir varchar(255) NOT NULL default '',
    shell varchar(16) NOT NULL default '/sbin/nologin',
    count int(11) NOT NULL default '0',
    accessed datetime NOT NULL default '0000-00-00 00:00:00',
    modified datetime NOT NULL default '0000-00-00 00:00:00',
    db_id int(10) unsigned,
    PRIMARY KEY (id),
    UNIQUE KEY userid (userid),
    FOREIGN KEY (db_id) REFERENCES client_databases(id)
);
