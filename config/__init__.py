try:
    import pymysql

    # Django mysqlclient versiyasini tekshiradi; PyMySQL ni mos qilib ko'rsatamiz
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.install_as_MySQLdb()
except ImportError:  # sqlite bilan ishlaganda kerak emas
    pass
