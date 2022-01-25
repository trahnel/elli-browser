document = {
  querySelectorAll: function (s) {
    var handles = call_python('querySelectorAll', s);
    return handles.map(function (h) {
      return new Node(h);
    });
  },
};

console = {
  log: function (x) {
    call_python('log', x);
  },
};

var LISTENERS = {};
function Node(handle) {
  this.handle = handle;
}

Node.prototype.getAttribute = function (attr) {
  return call_python('getAttribute', this.handle, attr);
};

Node.prototype.addEventListener = function (type, listener) {
  if (!LISTENERS[this.handle]) {
    LISTENERS[this.handle] = {};
  }
  var dict = LISTENERS[this.handle];
  if (!dict[type]) {
    dict[type] = [];
  }
  var list = dict[type];
  list.push(listener);
};

Node.prototype.dispatchEvent = function (evt) {
  var type = evt.type;
  var handle = this.handle;
  var list = (LISTENERS[handle] && LISTENERS[handle][type]) || [];
  for (var i = 0; i < list.length; i++) {
    list[i].call(this, evt);
  }
  return evt.do_default;
};

function Event(type) {
  this.type = type;
  this.do_default = true;
}

Event.prototype.preventDefault = function () {
  this.do_default = false;
};
Object.defineProperty(Node.prototype, 'innerHTML', {
  set: function (s) {
    call_python('innerHTML_set', this.handle, s.toString());
  },
});
