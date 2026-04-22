const grid = document.getElementById('grid');
const tpl = document.getElementById('card-tpl');

async function fetchDevices(){
  const res = await fetch('/api/devices');
  if(!res.ok) return [];
  return await res.json();
}

function render(devs){
  grid.innerHTML = '';
  devs.forEach(d=>{
    const node = tpl.content.cloneNode(true);
    node.querySelector('.name').textContent = d.name;
    node.querySelector('.type').textContent = d.type || '';
    node.querySelector('.ip').textContent = d.ip;
    node.querySelector('.desc').textContent = `User: ${d.user}`;
    const card = node.querySelector('.card');
    const btnCheck = node.querySelector('.btn-check');
    const btnReboot = node.querySelector('.btn-reboot');
    const btnDetails = node.querySelector('.btn-details');

    btnCheck.addEventListener('click', async ()=>{
      btnCheck.disabled = true;
      btnCheck.textContent = '...';
      const r = await fetch(`/api/devices/${encodeURIComponent(d.name)}/check`, {method:'POST'});
      if(r.ok){
        const json = await r.json();
        alert(`${d.name} reachable: ${json.reachable}`);
      } else {
        alert('Error checking device');
      }
      btnCheck.disabled = false;
      btnCheck.textContent = 'Check';
    });

    btnReboot.addEventListener('click', async ()=>{
      if(!confirm(`Reboot ${d.name}?`)) return;
      btnReboot.disabled = true;
      const r = await fetch(`/api/devices/${encodeURIComponent(d.name)}/reboot`, {method:'POST'});
      if(r.ok){
        alert('Reboot command sent');
      } else {
        const text = await r.text();
        alert('Error: '+text);
      }
      btnReboot.disabled = false;
    });

    btnDetails.addEventListener('click', async ()=>{
      const r = await fetch(`/api/devices/${encodeURIComponent(d.name)}/check`, {method:'POST'});
      if(r.ok){
        const j = await r.json();
        alert(JSON.stringify(j, null, 2));
      } else alert('Error');
    });

    grid.appendChild(node);
  });
}

document.getElementById('refresh').addEventListener('click', async ()=>{
  const devs = await fetchDevices();
  render(devs);
});

// initial load
fetchDevices().then(render);
