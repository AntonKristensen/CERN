# ------------------------------------------------------------------------------------------------
# This is an automatic backup of the script that processed this task, made at the end of the task.
# Please note that the same script may process multiple tasks, so it may show up multiple times.
# The original location and name of the script was /home/bashiri/cviv/c/scripts/load_df.py.
# LIP-PPS-Run-Manager v 0.3.0 was used as the managing backend.
# The backup was created on 2023-12-04 11:33:38.764713.
# A copy of all the local variables at the time the __enter__ method of the task started:
#   Pedro: RunManager(PosixPath('/home/bashiri/cviv/c/scripts/data/CVIV-Run0188'))
#   db_path: PosixPath('/home/bashiri/cviv/c/scripts/data/run_db.sqlite')
#   run_name: 'CVIV-Run0188'
#   output_path: PosixPath('/home/bashiri/cviv/c/scripts/data')
#   backup_path: PosixPath('/home/bashiri/cviv/c/scripts/data/backup')
# ------------------------------------------------------------------------------------------------
#############################################################################
# zlib License
#
# (C) 2023 Cristóvão Beirão da Cruz e Silva <cbeiraod@cern.ch>
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.
#############################################################################

from pathlib import Path
import logging
import sqlite3
import pandas
import datetime

import lip_pps_run_manager as RM

import utilities

def load_df_task(Pedro: RM.RunManager, db_path: Path, run_name: str, output_path: Path, backup_path: Path):
    with Pedro.handle_task("load_df_task", drop_old_data=True) as Lilly:
        with sqlite3.connect(db_path) as sql_conn:
            utilities.enable_foreign_keys(sql_conn)

            run_info_sql = f"SELECT `RunID`,`RunName`,`path`,`type`,`sample`,`pixel row`,`pixel col`,`begin location`,`end location`,`start` FROM 'RunInfo' WHERE `RunName`=?;"
            res = sql_conn.execute(run_info_sql, [run_name]).fetchall()
            if len(res) == 0:
                raise RuntimeError(f"Unable to find information in the database for run {run_name}")

            runId = res[0][0]
            run_file_path = Path(res[0][2])
            run_type = utilities.CVIV_Types(res[0][3])
            sample = res[0][4]
            pixel_row = res[0][5]
            pixel_col = res[0][6]
            begin_location = res[0][7]
            end_location = res[0][8]
            start = datetime.datetime.fromisoformat(res[0][9])

            if not run_file_path.exists() or not run_file_path.is_file():
                orig_run_file_path = run_file_path
                extension = "dat"
                if run_type == utilities.CVIV_Types.IV or run_type == utilities.CVIV_Types.IV_Two_Probes:
                    extension = 'iv'
                elif run_type == utilities.CVIV_Types.CV:
                    extension = 'cv'
                run_file_path = backup_path / (res[0][1] + "." + extension)

            if not run_file_path.exists() or not run_file_path.is_file():
                raise RuntimeError(f"Could not find the run file for run {run_name}")

            cols = None
            # TODO: Missing standard IV
            if run_type == utilities.CVIV_Types.IV_Two_Probes:
                cols = ["Bias Voltage [V]", "Total Current [A]", "Pad Current [A]"]
            elif run_type == utilities.CVIV_Types.CV:
                cols = ["Voltage [V]", "Capacitance [F]", "Conductivity [S]", "Bias Voltage [V]", "Pad Current [A]"]
            else:
                raise RuntimeError(f"Columns are not defined for the run type {run_type}")

            df = pandas.read_csv(
                                run_file_path,
                                sep = "\t",
                                names = cols,
                                skiprows = begin_location + 1,
                                nrows = end_location - begin_location - 1,
                                 )

            for col in df.columns:
                if col in ["Capacitance [F]", "Conductivity [S]", "Legend"]:
                    continue
                df[col] = -df[col]

            if run_type == utilities.CVIV_Types.CV:
                df["InverseCSquare"] = 1/(df["Capacitance [F]"]**2)

            tmp = df['Bias Voltage [V]'].diff()
            tmp.fillna(tmp[1], inplace = True)
            tmp.loc[tmp == 0] = tmp.shift(-1)
            df['Ascending'] = (tmp > 0)
            df['Descending'] = (tmp < 0)

            df['Is Coarse'] = False
            if start > datetime.datetime(2023, 8, 1, 0, 0, 0):
                df.loc[:19, 'Is Coarse'] = True # 20-1 because indexing from 0
                #df['Is Coarse'].iloc[:20] = True
            #print(df.to_string())

            # df.to_feather(Lilly.path_directory / "data.feather")
            df.to_csv(Lilly.path_directory / "data.csv", index=False)

            # print(df)

def script_main(
                db_path: Path,
                run_name: str,
                output_path: Path,
                backup_path: Path,
                already_exists: bool = False,
                ):
    logger = logging.getLogger('load_df')

    run_file_path: Path = None
    with sqlite3.connect(db_path) as sql_conn:
        utilities.enable_foreign_keys(sql_conn)

        run_info_sql = f"SELECT `RunName`,`path`,`type`,`name`,`RunID` FROM 'RunInfo' WHERE `RunName`=?;"
        res = sql_conn.execute(run_info_sql, [run_name]).fetchall()

        if not backup_path.exists():
            backup_path.mkdir()

        if len(res) > 0:
            run_file_path = Path(res[0][1])
            if not run_file_path.exists() or not run_file_path.is_file():
                orig_run_file_path = run_file_path
                extension = "dat"
                if res[0][2] == utilities.CVIV_Types.IV.value or res[0][2] == utilities.CVIV_Types.IV_Two_Probes.value:
                    extension = 'iv'
                elif res[0][2] == utilities.CVIV_Types.CV.value:
                    extension = 'cv'
                run_file_path = backup_path / (res[0][0] + "." + extension)
                if not run_file_path.exists() or not run_file_path.is_file():
                    print(f"The original run file ({orig_run_file_path}) is no longer available, and the backup file ({run_file_path}) could not be found. Recreating the backup file from database.")

                    res = sql_conn.execute("SELECT `Data` FROM 'runBackup' WHERE `RunID`=?;", [res[0][4]]).fetchall()
                    with run_file_path.open("wb") as file:
                        file.write(res[0][0])

                    if not run_file_path.exists() or not run_file_path.is_file():
                        raise RuntimeError(f"Unable to recreate the backup run file ({run_file_path}).")
    if run_file_path is None:
        raise RuntimeError(f"Could not find a run file in the run database for run {run_name}")

    with RM.RunManager(output_path / run_name) as William:
        William.create_run(raise_error=not already_exists)

        load_df_task(William, db_path, run_name, output_path, backup_path)

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='load_df.py',
                    description='This script loads the run data into a dataframe for later use',
                    #epilog='Text at the bottom of help'
                    )

    parser.add_argument(
        '-d',
        '--dbPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the database directory, where the run database is placed. Default: ./data',
        default = "./data",
        dest = 'db_path',
    )
    parser.add_argument(
        '-b',
        '--backupPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the data backup directory. If not set, a sub-directory in the database directory is assumed.',
        #required = True,
        dest = 'backup_path',
    )
    parser.add_argument(
        '-o',
        '--outputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the output directory.',
        required = True,
        dest = 'output_path',
    )
    parser.add_argument(
        '-r',
        '--run',
        metavar = 'RUN_NAME',
        type = str,
        help = 'The name of the run to process. The run database information will be used to find the run',
        required = True,
        dest = 'run',
    )
    parser.add_argument(
        '-l',
        '--log-level',
        help = 'Set the logging level. Default: WARNING',
        choices = ["CRITICAL","ERROR","WARNING","INFO","DEBUG","NOTSET"],
        default = "WARNING",
        dest = 'log_level',
    )
    parser.add_argument(
        '--log-file',
        help = 'If set, the full log will be saved to a file (i.e. the log level is ignored)',
        action = 'store_true',
        dest = 'log_file',
    )

    args = parser.parse_args()

    if args.log_file:
        logging.basicConfig(filename='logging.log', filemode='w', encoding='utf-8', level=logging.NOTSET)
    else:
        if args.log_level == "CRITICAL":
            logging.basicConfig(level=50)
        elif args.log_level == "ERROR":
            logging.basicConfig(level=40)
        elif args.log_level == "WARNING":
            logging.basicConfig(level=30)
        elif args.log_level == "INFO":
            logging.basicConfig(level=20)
        elif args.log_level == "DEBUG":
            logging.basicConfig(level=10)
        elif args.log_level == "NOTSET":
            logging.basicConfig(level=0)

    db_path: Path = args.db_path
    if not db_path.exists():
        raise RuntimeError("The database path does not exist")
    db_path = db_path.absolute()
    db_path = db_path / "run_db.sqlite"
    if not db_path.exists() or not db_path.is_file():
        raise RuntimeError("The database file does not exist")

    backup_path: Path = args.backup_path
    # If the backup path is not set:
    if backup_path is None:
        backup_path = db_path.parent / 'backup'
    backup_path = backup_path.absolute()

    output_path: Path = args.output_path
    if not output_path.exists() or not output_path.is_dir():
        logging.error("You must define a valid data output path")
        exit(1)
    output_path = output_path.absolute()

    script_main(db_path, args.run, output_path, backup_path)

if __name__ == "__main__":
    main()