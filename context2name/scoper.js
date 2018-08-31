var esprima = require('esprima');
var estraverse = require('estraverse');
var fs = require('fs');

var HOP = function (obj, prop) {
    return Object.prototype.hasOwnProperty.call(obj, prop);
};

function isArr(val) {
    return Object.prototype.toString.call(val) === '[object Array]';
}


function MAP(arr, fun) {
    var len = arr.length;
    if (!isArr(arr)) {
        throw new TypeError();
    }
    if (typeof fun !== "function") {
        throw new TypeError();
    }

    var res = new Array(len);
    for (var i = 0; i < len; i++) {
        if (i in arr) {
            res[i] = fun(arr[i]);
        }
    }
    return res;
}

if (!String.prototype.endsWith) {
    String.prototype.endsWith = function (searchString, position) {
        var subjectString = this.toString();
        if (typeof position !== 'number' || !isFinite(position) || Math.floor(position) !== position || position > subjectString.length) {
            position = subjectString.length;
        }
        position -= searchString.length;
        var lastIndex = subjectString.lastIndexOf(searchString, position);
        return lastIndex !== -1 && lastIndex === position;
    };
}

var CONTEXT = {
    IGNORE: 2,
    NORMAL: 9
};

function transformAst(object, visitorPost, visitorPre, context) {
    var key, child, type, newContext;

    type = object.type;
    if (visitorPre && HOP(visitorPre, type)) {
        visitorPre[type](object, context);
    }

    for (key in object) {
        child = object[key];
        if (typeof child === 'object' && child !== null && key !== "scope" && key !== "scopeid" && key !== "curScope") {
            if (type === 'MemberExpression' && key === 'property' && object.computed !== true) {
                newContext = CONTEXT.IGNORE;
            } else if (type === 'Property' && key === 'key') {
                newContext = CONTEXT.IGNORE;
            } else if (key === "label") {
                newContext = CONTEXT.IGNORE;
            } else {
                newContext = CONTEXT.NORMAL;
            }
            
            transformAst(child, visitorPost, visitorPre, newContext);
        }
    }

    if (visitorPost && HOP(visitorPost, type)) {
        visitorPost[type](object, context);
    }
}

function addScopes(ast) {

    function Scope(parent, isCatch) {
        this.id = Scope.counter++;
        this.vars = {};
        this.funLocs = {};
        this.funNodes = {};
        this.hasEval = false;
        this.hasArguments = false;
        this.parent = parent;
        this.isCatch = isCatch;
        this.children = [];
        if (parent)
            parent.children.push(this);

        // Specific to Context2Name
        this.usedInScopeMap = {}; // Maps an identifier to the children scopes it was used in
        this.origScopeMap = {}; // Maps an identifier use in this scope to its actual scope
        this.renamedVars = {};
        this.newNames = {};
    }

    Scope.counter = 0;

    Scope.prototype.addVar = function (name, type, loc, node) {
        var tmpScope = this;
        while(tmpScope.isCatch && type !== 'catch') {
            tmpScope = tmpScope.parent;
        }

        if (tmpScope.vars[name] !== 'arg') {
            tmpScope.vars[name] = type;
        }

        if (type === 'defun') {
            tmpScope.funLocs[name] = loc;
            tmpScope.funNodes[name] = node;
        }
    };

    Scope.prototype.hasOwnVar = function (name) {
        var s = this;
        if (s && HOP(s.vars, name))
            return s.vars[name];
        return null;
    };

    Scope.prototype.getScope = function (name, funcDec) {
        var s = this;
        if (funcDec && funcDec === true) {
            s = s.parent;
        }

        while (s !== null) {
            if (HOP(s.vars, name))
                return s;
            s = s.parent;
        }
        return null;
    };

    Scope.prototype.hasVar = function (name) {
        var s = this;
        while (s !== null) {
            if (HOP(s.vars, name))
                return s.vars[name];
            s = s.parent;
        }
        return null;
    };

    // Used for Context2Name
    Scope.prototype.alreadyUsed = function(name, origName) {
        if (this.alreadyUsedInScopeBelow(name, -1)) return true;

        var uses = this.usedInScopeMap[origName];
        for (var scope of uses) {
            if (scope.alreadyUsedInScopeBelow(name, -1)) return true;
        }

        for (var scope of uses) {
            if (scope.id !== this.id) {
                var tmpScope = scope;
                while (tmpScope.id !== this.id) {
                    if (HOP(tmpScope.newNames, name))
                        return true;

                    tmpScope = tmpScope.parent;
                }
            }
        }

        return false;
    }

    Scope.prototype.alreadyUsedInScopeBelow = function (name, sid) {
        if (HOP(this.origScopeMap, name)) {
            if (sid == -1) return true;
            else if (this.origScopeMap[name] <= sid) return true;
        }

        if (sid == -1) sid = this.id;
        for (var i = 0; i < this.children.length; i++) {
            if (this.children[i].alreadyUsedInScopeBelow(name, sid)) return true;
        }

        return false;
    }

    // Used for Context2Name
    Scope.prototype.renameVar = function (name, newName) {
        var s = this;
        s.renamedVars[name] = newName;
        s.newNames[newName] = 1;
        if (HOP(this.usedInScopeMap, name)) {
            var uses = this.usedInScopeMap[name];
            for (var scope of uses) {
                scope.origScopeMap[newName] = s.id;
            }
        }

        s.origScopeMap[newName] = s.id;
    };

    // Used for Context2Name
    Scope.prototype.getRenaming = function(name) {
        var s = this;
        if (HOP(s.renamedVars, name)) {
            return s.renamedVars[name];
        } else {
            return name;
        }
    };

    Scope.prototype.isGlobal = function (name) {
        var s = this;
        while (s !== null) {
            if (HOP(s.vars, name) && s.parent !== null) {
                return false;
            }
            s = s.parent;
        }
        return true;
    };

    Scope.prototype.addEval = function () {
        var s = this;
        while (s !== null) {
            s.hasEval = true;
            s = s.parent;
        }
    };

    Scope.prototype.addArguments = function () {
        var s = this;
        while (s !== null) {
            s.hasArguments = true;
            s = s.parent;
        }
    };

    Scope.prototype.usesEval = function () {
        return this.hasEval;
    };

    Scope.prototype.usesArguments = function () {
        return this.hasArguments;
    };


    var currentScope = null;
    var rootScope = null;

    function handleFun(node) {
        var oldScope = currentScope;
        currentScope = new Scope(currentScope);

        if (node.type === 'FunctionDeclaration') {
            if (oldScope != null) {
                node.id.curScope = oldScope;
            } else {
            }
            oldScope.addVar(node.id.name, "defun", node.range, node);
            MAP(node.params, function (param) {
                currentScope.addVar(param.name, "arg");
                param.curScope = currentScope;
            });
        } else if (node.type === 'FunctionExpression') {
            if (node.id !== null) {
                currentScope.addVar(node.id.name, "lambda");
                node.id.curScope = currentScope;
                currentScope = new Scope(currentScope);
                node.scope = currentScope;
            }
            MAP(node.params, function (param) {
                currentScope.addVar(param.name, "arg");
                param.curScope = currentScope;
            });
        }
    }

    function handleVar(node) {
        currentScope.addVar(node.id.name, "var");
    }

    function handleID(node, context) {
        if (context === CONTEXT.IGNORE) return;
        if (node.curScope === undefined) {
            node.curScope = currentScope;
        }
    }

    function handleIDPost(node, context) {
        if (context === CONTEXT.IGNORE) return;
        if (node.scopeid === undefined && node.name !== undefined) {
            var curScope = node.curScope;
            if (!curScope.hasVar(node.name)) {
                //console.log("Adding implicit global " + node.name);
                rootScope.addVar(node.name, "implicit_global");
            }

            var scope = curScope.getScope(node.name);
            if (scope === null || scope === undefined) {
                // the identifier may be a default property. Shouldn't mess with it
                return;
            }

            node.scopeid = scope.id;
            node.scope = scope;

            if (scope.id === 0)
                curScope.origScopeMap[node.name] = 0;
            // For Context2Name
            if (!HOP(scope.usedInScopeMap, node.name)) 
                scope.usedInScopeMap[node.name] = new Set();

            scope.usedInScopeMap[node.name].add(curScope);
        }
    }

    function handleCatch(node) {
        currentScope = new Scope(currentScope, true);
        node.scope = currentScope;
        currentScope.addVar(node.param.name, "catch");
        node.scope = currentScope;
        node.param.curScope = currentScope;
    }

    function popScope(node) {
        currentScope = currentScope.parent;
    }

    var visitorPre = {
        'Program': function(node) { currentScope = new Scope(currentScope); rootScope = currentScope;},
        'FunctionDeclaration': handleFun,
        'FunctionExpression': handleFun,
        'VariableDeclarator': handleVar,
        'CatchClause': handleCatch,
        'Identifier' : handleID,
    };

    var visitorPost = {
        'Program': popScope,
        'FunctionDeclaration': popScope,
        'FunctionExpression': function(node) { popScope(); if (node.id !== null) { popScope(); }},
        'CatchClause': function(node) { popScope(); },
    };

    transformAst(ast, visitorPost, visitorPre);

    var visitorPre = {
        'Identifier' : handleIDPost
    };

    transformAst(ast, {}, visitorPre);
}

module.exports = {
    addScopes2AST : function (ast) {
        addScopes(ast);
    }
}
