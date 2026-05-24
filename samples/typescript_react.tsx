import React, { useState, useEffect } from 'react';

export function UserList(props: any) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/users')
      .then(res => res.json())
      .then(data => {
        setUsers(data);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {users.map((u: any) => (
        <div onClick={() => props.onSelect(u.id)}>
          {u.name} - {u.email}
        </div>
      ))}
    </div>
  );
}
