# SEGD to SEG-Y Converter

A tool to convert raw **SEG-D** seismic data into standard **SEG-Y (Big-Endian)** format for seismic processing software. The converter utilizes Python multiprocessing to process large batches of files in parallel.

## Usage

### Method 1: Standalone Executable (GUI)
This method requires no installation or command-line knowledge.

1. Navigate to the `dist/` folder.
2. Double-click `batch_convert.exe`.
3. A dialog window will appear. Follow the prompts to:
   - Select the input folder containing your `.SEGD` files.
   - Select the output folder where the converted `.sgy` files will be saved.
4. The conversion will start automatically.

### Method 2: Command Line (CLI)
For advanced users who prefer the terminal or want to integrate the tool into other scripts. Requires Python 3.

1. Open a terminal in the project directory.
2. Run the following command:
   ```bash
   python batch_convert.py -i <input_folder> -o <output_folder>
   ```
   **Example:**
   ```bash
   python batch_convert.py -i data/ -o output_final/
   ```
3. (Optional) Specify the number of CPU cores to use with the `-w` flag:
   ```bash
   python batch_convert.py -i data/ -o output_final/ -w 4
   ```

## Features
- **Resilient Processing**: If a file is corrupted, the program will skip it, log the issue to `error_log.txt` in the output folder, and continue processing the rest of the files.
- **Recursive Search**: The tool automatically finds all `.SEGD` files, including those located in subdirectories of the selected input folder.

## Core Files
- `batch_convert.py`: Main script handling the GUI fallback, CLI arguments, and multiprocessing.
- `segd2segy.py`: The core conversion engine.
- `dist/batch_convert.exe`: The compiled Windows executable.
