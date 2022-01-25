function lengthCount() {
  var value = this.getAttribute('value');
  console.log('From JS, input length is ' + value.length);
}

inputs = document.querySelectorAll('input');
for (var i = 0; i < inputs.length; i++) {
  inputs[i].addEventListener('keydown', lengthCount);
}
