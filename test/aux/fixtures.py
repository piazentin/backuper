from backuper.implementation import models

stored_text_file1 = models.StoredFile(
    "text_file1.txt",
    "fef9161f9f9a492dba2b1357298f17897849fefc",
    "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
    "",
    False,
)
stored_text_file1_copy = models.StoredFile(
    "text_file1 copy.txt",
    "fef9161f9f9a492dba2b1357298f17897849fefc",
    "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
    "",
    False,
)
stored_text_file1_copy_updated = models.StoredFile(
    "text_file1 copy.txt",
    "7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
    "7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
    "",
    False,
)
stored_starry_night = models.StoredFile(
    "subdir/starry_night.png",
    "07c8762861e8f1927708408702b1fd747032f050",
    "0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
    "",
    False,
)
stored_license = models.StoredFile(
    "LICENSE",
    "10e4b6f822c7493e1aea22d15e515b584b2db7a2",
    "1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
    "",
    False,
)
stored_license_updated = models.StoredFile(
    "LICENSE",
    "5b5174193c004d8f27811b961fbaa545b5460f2a",
    "5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
    "",
    False,
)
stored_license_zip = models.StoredFile(
    "LICENSE",
    "10e4b6f822c7493e1aea22d15e515b584b2db7a2",
    "1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2.zip",
    "",
    True,
)
stored_license_zip_updated = models.StoredFile(
    "LICENSE",
    "5b5174193c004d8f27811b961fbaa545b5460f2a",
    "5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a.zip",
    "",
    True,
)

new_backup_stored_files = {
    stored_text_file1,
    stored_text_file1_copy,
    stored_starry_night,
    stored_license,
}
new_backup_stored_files_zip = {
    stored_text_file1,
    stored_text_file1_copy,
    stored_starry_night,
    stored_license_zip,
}
update_stored_files = {
    stored_text_file1,
    stored_text_file1_copy_updated,
    stored_license_updated,
}
update_stored_files_zip = {
    stored_text_file1,
    stored_text_file1_copy_updated,
    stored_license_zip_updated,
}

new_backup_dirs = {models.DirEntry("subdir"), models.DirEntry("subdir/empty dir")}
update_dirs = set()

new_backup_db = {
    "dirs": new_backup_dirs,
    "stored_files": new_backup_stored_files,
}
new_backup_with_zip_db = {
    "dirs": new_backup_dirs,
    "stored_files": new_backup_stored_files_zip,
}
update_backup = {
    "dirs": update_dirs,
    "stored_files": update_stored_files,
}
update_backup_with_zip = {"dirs": update_dirs, "stored_files": update_stored_files_zip}
