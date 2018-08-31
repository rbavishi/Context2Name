var scoper = require(__dirname + '/scoper.js');
var pq = require('js-priority-queue');

var fs = require('fs');
var esprima = require('esprima');
var estraverse = require('estraverse');
var syncrequest = require('sync-request');
var escodegen = require('escodegen');

var ArgumentParser = require('argparse').ArgumentParser;

var HOP = function (obj, prop) {
    return Object.prototype.hasOwnProperty.call(obj, prop);
};

function extractSequences(ast, tokens, rangeToTokensIndexMap) {
    var sequences = [];

    function appendToken(arr, index, i) {
        var t, prev;
        if (i < 0) {
            arr.push("0START");
        } else if (i >= tokens.length) {
            arr.push("0END");
        } else if (i !== index) {
            t = tokens[i];
            if (t === undefined) {
                console.log(t);
            }
            prev = tokens[i - 1];
            if (t.type === "Identifier" && !(prev && prev.value === "." && prev.type === "Punctuator")) {
                if (t.hasOwnProperty("scopeid")) {
                    arr.push("1ID:" + t.scopeid + ":" + t.value);
                } else {
                    arr.push("1ID:-1:" + t.value);
                }
            } else if (!(t.value === "(" || t.value === ")" || t.value === ".")) {
                arr.push(t.value);
            }
        }
    }

    function appendVarUsage(node) {
        var index = rangeToTokensIndexMap[node.range + ""];
        var p = tokens[index - 1];
        if (p && p.type === "Punctuator" && p.value === ".") {
            return;
        }

        if (node.scopeid > 0) {
            var arr = [];
            var i, t, prev;
            for (i = index - 1; arr.length < WIDTH; i--) {
                appendToken(arr, index, i);
            }
            arr.reverse();
            arr.unshift(node.scope);
            arr.unshift(node.name);
            arr.unshift(node.scopeid);
            for (i = index + 1; arr.length < 3 + 2 * WIDTH; i++) {
                appendToken(arr, index, i);
            }
            sequences.push(arr);
        }
    }

    // Transfer the scopeids to the tokens as well

    estraverse.traverse(ast, {
        enter : function (node) {
            if (node.type === "Identifier") {
                if (node.name !== undefined && node.name !== "undefined" && node.name !== "NaN" && node.name !== "Infinity") {

                    if (node.scopeid !== undefined) {
                        var index = rangeToTokensIndexMap[node.range + ""];
                        var token = tokens[index];
                        token.scopeid = node.scopeid;
                    }
                }
            } 
        }
    });

    // Create the sequences

    estraverse.traverse(ast, {
        enter : function (node) {
            if (node.type === "Identifier") {
                if (node.name !== undefined && node.name !== "undefined" && node.name !== "NaN" && node.name !== "Infinity") {

                    appendVarUsage(node);
                }
            }
        }
    });

    return sequences;
}

function writeSequences(sequences, outFile, fname, mode) {
    var seqMap = new Object(null);
    for (var i = 0; i < sequences.length; i++) {
        var sequence = sequences[i];
        var key = "" + sequence[0] + sequence[1];
        var val = seqMap[key];
        if (!val) {
            seqMap[key] = val = ["", sequence[1], sequence[0], sequence[2]];
        }
        for (var j = 3; j < sequence.length; j++) {
            var token = sequence[j] + "";
            var tokens = token.split(/(\s+)/);
            token = tokens[0];
            if (val[0].length > 0) {
                val[0] = val[0] + " ";
            }
            val[0] = val[0] + token;
        }
    }

    if (mode && mode === "recovery") {
        var testcases = [];
        var scopes = [];
        for (var k in seqMap) {
            if (seqMap.hasOwnProperty(k)) {
                scopes.push(seqMap[k][3]);
                testcases.push(fname.replace(/ /g,"_") + " 1ID:" + seqMap[k][2] + ":" + seqMap[k][1] + " " + seqMap[k][0]);
            }
        }

        return [testcases, scopes];

    } else {
        var logStream = fs.createWriteStream(outFile, {'flags': 'a'});
        for (var k in seqMap) {
            if (seqMap.hasOwnProperty(k)) {
                logStream.write(fname.replace(/ /g,"_") + " 1ID:" + seqMap[k][2] + ":" + seqMap[k][1] + " " + seqMap[k][0] + "\n");
            }
        }

        logStream.end();
    }
}

function recover(args, ast, testcases, scopes) {
    function isOk2Rename(origName, newName, scope) {
        // Check if any of the child scopes (including this) has a use of a variable called newName, belong
        // to this or a higher scope
        // Basic Idea : Don't shadow a variable
        return !(useStrictDirective && newName === "arguments") && !scope.alreadyUsed(newName, origName);
    }

    function rename(origName, newName, scope) {
        if (args.debug) 
            console.log("Renaming " + origName + " to " + newName + " in " + scope.id);

        // For all the uses of this variable, mark that newName is being used in that scope
        scope.renameVar(origName, newName);
    }

    if (testcases.length === 0) {
        // Nothing to do. The program stays as is.
        return 0;
    }

    var useStrictDirective = true;

    // Extract Directives
    for (var i = 0; i < ast.body.length; i++) {
        if (HOP(ast.body[i], "directive")) {
            if (ast.body[i].directive === "use strict")
                useStrictDirective = true;
        }
    }

    // Send to the server
    var response = syncrequest('POST', 'http://' + args.ip + ":" + args.port,
                { json : { 'tests' : testcases}});

    if (response.statusCode === 200) {
        // res format : [prediction_arrays, the original names in the file, runtime]
        // prediction arrays format : array of arrays, each inner array containing 10 tuples
        // inner prediction tuple format : [probability, new name, index of name in the original array of names]
        var res = JSON.parse(response.body.toString('utf-8'));

        // Begin assignment of new names using a priority queue
        var queue = new pq({ comparator: function(a, b) { return b[0] - a[0]; }});

        var next2use = []; // Captures the number of names tried for each variable
        for (var i = 0; i < res[1].length; i++) {
            queue.queue(res[0][i][0]); // the first prediction tuple for each variable
            next2use.push(1);
        }

        var unk_ctr = 0;

        while (queue.length !== 0) {
            var elem =  queue.dequeue();
            var origIdx = elem[2];
            var origName = res[1][origIdx].split(':')[2];
            var newName = elem[1];
            var curScope = scopes[origIdx];
            if (origName === "arguments")
                continue;

            if (isOk2Rename(origName, newName, curScope)) {
                rename(origName, newName, curScope);
            } else {
                if (next2use[origIdx] >= 10) { // No more predictions left
                    if (isOk2Rename(origName, origName, curScope)) { // This is needed, it's not trivial!
                        rename(origName, origName, curScope);
                    } else {
                        rename(origName, "C2N_" + unk_ctr + "_" + origName, curScope);
                        unk_ctr += 1;
                    }
                } else {
                    queue.queue(res[0][origIdx][next2use[origIdx]]);
                    next2use[origIdx] += 1;
                } 
            }
        }

        // Go over the AST and assign new names
        estraverse.traverse(ast, {
            enter : function(node) {
                if (node.type === "Identifier") {
                    if (node.name && node.scope && node.scopeid) {
                        if (node.scopeid > 0) {
                            if (node.isFuncName)
                                node.name = node.scope.getRenaming("$FUNC$" + node.name);
                            else
                                node.name = node.scope.getRenaming(node.name);

                        }
                    }
                }
            }
        });

        // All Done!
        return 0;

    } else {
        return -1;
    }

}

function processFile(args, fname, outFile) {
    try {
        if (!args.no_normalization)
            fname = fname.substr(0, fname.length-3) + ".normalized.js";

        var code = fs.readFileSync(fname, 'utf-8');
        var ast = esprima.parse(code, {tokens: true, range: true});
        var tokens = ast.tokens;
        
        // Create token2index map
        var rangeToTokensIndexMap = new Object(null);
        for (var i = 0; i < tokens.length; i++) {
            rangeToTokensIndexMap[tokens[i].range + ""] = i;
        }

        // Annotate nodes with scopes
        scoper.addScopes2AST(ast);

        // Extract Sequences
        var sequences = extractSequences(ast, tokens, rangeToTokensIndexMap);

        // Dump the sequences
        writeSequences(sequences, outFile, fname);

        console.log("[+] [" + success + "/" + failed + "] Processed file : " + fname);
        return 0;

    } catch (e) {
        if (args.debug)
            console.error(e.stack);        
        console.log("[-] [" + success + "/" + failed + "] Failed to process file : " + fname);
        return -1;
    }
}

function recoverFile(args, fname, outFile) {
    try {
        var code = fs.readFileSync(fname, 'utf-8');
        var startTime = process.hrtime();
        var ast = esprima.parse(code, {tokens: true, range: true});
        var tokens = ast.tokens;
        
        // Create token2index map
        var rangeToTokensIndexMap = new Object(null);
        for (var i = 0; i < tokens.length; i++) {
            rangeToTokensIndexMap[tokens[i].range + ""] = i;
        }

        // Annotate nodes with scopes
        scoper.addScopes2AST(ast);

        // Extract Sequences
        var sequences = extractSequences(ast, tokens, rangeToTokensIndexMap);
        var res = writeSequences(sequences, null, fname, "recovery");
        var testcases = res[0];
        var scopes = res[1];
        var isFuncs = res[2];

        // Start Recovery
        recover(args, ast, testcases, scopes, isFuncs);
        var elapsedTime = process.hrtime(startTime);
        elapsedTime = elapsedTime[0] * 1000 + elapsedTime[1]/1000000;
        if (args.ext)
            args.outfile = fname.substr(0, fname.length-6) + args.ext;

        if (args.outfile.endsWith(".js")) {
            if (args.stats)
                fs.writeFileSync(args.outfile.substr(0, args.outfile.length-3) + ".timing.stats", "Time : " + elapsedTime);
            fs.writeFileSync(args.outfile, escodegen.generate(ast));
        } else {
            if (args.stats)
                console.log("Time : " + elapsedTime);
            console.log(escodegen.generate(ast));
        }

        console.log("[+] [" + success + "/" + failed + "] Processed file : " + fname);
        return 0;

    } catch (e) {
        console.log("[-] [" + success + "/" + failed + "] Failed to recover file : " + fname);
        console.error(e.stack);
        return -1;
    }
}

var parser = new ArgumentParser({addHelp : true, description: 'Context2Name Client'});
parser.addArgument(
    ['--ip'],
    {
        help : 'IP Address of the server. Required in recovery mode.',
        defaultValue : '127.0.0.1'
    }
);

parser.addArgument(
    ['--port'],
    {
        help : 'Port for the server. Required in recovery mode',
        defaultValue : '8080'
    }
);

parser.addArgument(
    ['-l', '--listmode'],
    {
        action : 'storeTrue',
        help : 'Use input file as a list of files',
        defaultValue : false
    }
);

parser.addArgument(
    ['-f', '--file'],
    {
        help : 'File to work on',
        required : true,
        dest : 'inpFile'
    }
);

parser.addArgument(
    ['-d', '--debug'],
    {
        action : 'storeTrue',
        help : 'Debugging mode',
        defaultValue : false

    }
);

parser.addArgument(
    ['-r', '--recovery'],
    {
        action : 'storeTrue',
        help : 'Recovery Mode (Default = False)',
        defaultValue : false

    }
);

parser.addArgument(
    ['-s', '--stats'],
    {
        action : 'storeTrue',
        help : 'Collect relevant stats (Applicable only in recovery mode)',
        defaultValue : false

    }
);

parser.addArgument(
    ['--ext'],
    {
        action : 'store',
        //type : 'str',
        help : 'Extension to use for the recovered file (Default = null). Assumes that the filename passed ends in min.js',
        defaultValue : null
    }
);

parser.addArgument(
    ['-t', '--training-data'],
    {
        action : 'storeTrue',
        help : 'Training Mode. Creates the data to use for training. (Default = True)',
        defaultValue : true
    }
);

parser.addArgument(
    ['-w', '--width'],
    {
        action : 'store',
        type : 'int',
        help : 'Width of the contexts to use (Default : 5)',
        defaultValue : 5
    }
);

parser.addArgument(
    ['--no-normalization'],
    {
        action : 'storeTrue',
        help : "Don't use normalized versions of the input JS files in training data generation mode. Not recommended",
        defaultValue : false
    }
);

parser.addArgument(
    ['-a', '--append-mode'],
    {
        help : 'Append Mode. Useful while constructing training data.',
        required : false,
        action : 'storeTrue',
        defaultValue : false
    }
);

parser.addArgument(
    ['--outfile'],
    {
        help : 'Output File (Applicable only in training data extraction mode)',
        defaultValue : 'output.csv'
    }
);

var args = parser.parseArgs();
if (!args.append_mode) {
    var logStream = fs.createWriteStream(args.outfile, {'flags': 'w'});
    logStream.end();
}

var WIDTH = args.width;

if (args.recovery) {
    var success = 0;
    var failed = 0;
    if (args.listmode) {
        var readline = require('readline');

        var rl = readline.createInterface({
            input: fs.createReadStream(args.inpFile)
        });

        rl.on('line', function (line) {
            var s = recoverFile(args, line, args.outfile);
            if (s == 0) success += 1;
            else failed += 1;
        });

    } else {
        recoverFile(args, args.inpFile, args.outfile);
    }

} else {
    var success = 0;
    var failed = 0;
    if (args.listmode) {
        var readline = require('readline');

        var rl = readline.createInterface({
            input: fs.createReadStream(args.inpFile)
        });

        rl.on('line', function (line) {
            var s = processFile(args, line, args.outfile);
            if (s == 0) success += 1;
            else failed += 1;
        });
    } else {
        processFile(args, args.inpFile, args.outfile);
    }
}
