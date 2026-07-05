'use client';

import { createAvatar } from '@dicebear/core';
import { loreleiNeutral } from '@dicebear/collection';
import Image from 'next/image';
import { useMemo } from 'react';

type ProfileAvatarProps = {
  name: string;
  email?: string;
  className?: string;
};

export default function ProfileAvatar({ name, email, className }: ProfileAvatarProps) {
  const avatar = useMemo(() => {
    return createAvatar(loreleiNeutral, {
      seed: email || name,
      backgroundColor: ['c5ebe1', 'c6ddf6', 'fad7cd', 'fff0eb'],
      radius: 22,
    }).toDataUri();
  }, [email, name]);

  return (
    <Image
      src={avatar}
      alt={`${name}'s avatar`}
      className={className}
      draggable={false}
      width={96}
      height={96}
      unoptimized
    />
  );
}
