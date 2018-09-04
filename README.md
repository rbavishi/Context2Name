## Context2Name

The paper can be found [here](http://software-lab.org/publications/Context2Name_TR_Mar2018.pdf)

The training and testing dataset is a derivative of the [js150](https://www.sri.inf.ethz.ch/js150.php) dataset. Duplicates and common entries between the training and testing set have been removed.

compare.jar is a slightly modified version of the [JSNice jar distribution](https://files.sri.inf.ethz.ch/jsniceartifact/index.html) and is primarily used for evaluating performance i.e. accuracy of predicted names given the ground-truth. The primary change is the disabling of exclusion of files based on their size, and computation of some additional stats such as number of unique names recovered etc. 

The following sections state the commands to be used for various scenarios.

### Preparing the corpus

##### This involves normalization and minification

```
python3 data_scripts/prepare_corpus.py --minify --force "eval_list.txt" # Minification
python3 data_scripts/prepare_corpus.py --minify --no-mangle --force "eval_list.txt" # Normaliation
```

```
python3 data_scripts/prepare_corpus.py --minify --force "training_list.txt" # Minification
python3 data_scripts/prepare_corpus.py --minify --no-mangle --force "training_list.txt" # Normaliation
```

### Training Context2Name

##### First create training.csv and eval.csv
```
node context2name/c2n_client.js -l -f "eval_list.txt" --outfile "eval.csv"
node context2name/c2n_client.js -l -f "training_list.txt" --outfile "training.csv"
```

##### Start training
```
python3 context2name/training.py
```

### Evaluating Context2Name

```
npm install esprima escodegen estraverse sync-request argparse js-priority-queue
python3 context2name/c2n_server.py &
node context2name/c2n_client.js -l -f "eval_list.txt" -r -s --ext "c2n.js"
```

#### Analysis of all tools

First make sure that the output of JSNaughty is stored as *.jsnaughty.js and its timing results are stored as *.jsnaughty.timing.stats

##### Evaluating JSNice
```
java -jar compare.jar --eval_jsnice --jsnice_features=ASTREL,NODEFLAG,ARGALIAS,FNAMES --jsnice_infer=NAMES --use_inp_file_list eval_list.txt --save_recovered_files --print_stats > log_analysis.jsnice 
```

##### Evaluating Context2Name
```
java -jar compare.jar --eval_jsnice --jsnice_features=ASTREL,NODEFLAG,ARGALIAS,FNAMES --jsnice_infer=NAMES --use_inp_file_list eval_list.txt --eval_metrics_only --custom_ext "c2n" --print_stats > log_analysis.c2n
```

##### Evaluating JSNaughty
```
java -jar compare.jar --eval_jsnice --jsnice_features=ASTREL,NODEFLAG,ARGALIAS,FNAMES --jsnice_infer=NAMES --use_inp_file_list eval_list.txt --eval_metrics_only --custom_ext "jsnaughty" --print_stats > log_analysis.jsnaughty
```


#### Creating CSVs which contain all the necessary information
```
python3 data_scripts/generate_csvs.py eval_list.txt
```
##### Get other stats
```
python3 data_scripts/analysis.py --accuracies --timing --filestats --venn --save_venn "venn_no_time_limit_weighted.png" --venn_weighted eval_list.txt
python3 data_scripts/analysis.py --accuracies --timing --filestats --venn --save_venn "venn_time_limit_weighted.png" --venn_weighted --tlimit 600000 eval_list.txt
```

