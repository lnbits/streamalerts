async def m001_initial(db):

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS streamalerts.services (
            id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            twitchuser TEXT NOT NULL,
            client_id TEXT NOT NULL,
            client_secret TEXT NOT NULL,
            wallet TEXT NOT NULL,
            onchain TEXT,
            servicename TEXT NOT NULL,
            authenticated BOOLEAN NOT NULL,
            token TEXT
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS streamalerts.donations (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            cur_code TEXT NOT NULL,
            sats {db.big_int} NOT NULL,
            amount FLOAT NOT NULL,
            service TEXT NOT NULL,
            posted BOOLEAN NOT NULL
        );
        """
    )
