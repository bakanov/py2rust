use std::cell::{Cell, RefCell};
use std::io::Read;

use crate::Result;

#[derive(PartialEq)]
pub struct Random {
    state: RefCell<[u32; 624]>,
    index: Cell<usize>,
}

impl Clone for Random {
    fn clone(&self) -> Self {
        Self {
            state: self.state.clone(),
            index: self.index.clone(),
        }
    }
}

impl Random {
    fn new(keys: &[u32]) -> Self {
        let mut state = [0u32; 624];
        state[0] = 19650218;
        for index in 1..624 {
            state[index] = 1812433253u32
                .wrapping_mul(state[index - 1] ^ (state[index - 1] >> 30))
                .wrapping_add(index as u32);
        }
        let mut index = 1usize;
        let mut key_index = 0usize;
        for _ in 0..624 {
            state[index] = (state[index]
                ^ ((state[index - 1] ^ (state[index - 1] >> 30)).wrapping_mul(1664525)))
            .wrapping_add(keys[key_index])
            .wrapping_add(key_index as u32);
            key_index += 1;
            if key_index == keys.len() {
                key_index = 0;
            }
            index += 1;
            if index == 624 {
                state[0] = state[623];
                index = 1;
            }
        }
        for _ in 0..623 {
            state[index] = (state[index]
                ^ ((state[index - 1] ^ (state[index - 1] >> 30)).wrapping_mul(1566083941)))
            .wrapping_sub(index as u32);
            index += 1;
            if index == 624 {
                state[0] = state[623];
                index = 1;
            }
        }
        state[0] = 0x80000000;
        Self {
            state: RefCell::new(state),
            index: Cell::new(624),
        }
    }

    fn next_u32(&self) -> u32 {
        if self.index.get() == 624 {
            let mut state = self.state.borrow_mut();
            let previous = *state;
            for index in 0..624 {
                let value =
                    (previous[index] & 0x80000000) | (previous[(index + 1) % 624] & 0x7fffffff);
                let other = if index < 227 {
                    previous[index + 397]
                } else {
                    state[index - 227]
                };
                state[index] = other ^ (value >> 1) ^ if value & 1 == 1 { 0x9908b0df } else { 0 };
            }
            self.index.set(0);
        }
        let index = self.index.get();
        let mut value = self.state.borrow()[index];
        self.index.set(index + 1);
        value ^= value >> 11;
        value ^= (value << 7) & 0x9d2c5680;
        value ^= (value << 15) & 0xefc60000;
        value ^ (value >> 18)
    }

    fn below(&self, upper: i64) -> i64 {
        if upper <= 1 {
            return 0;
        }
        let bits = 64 - (upper as u64).leading_zeros();
        let mask = if bits == 64 {
            u64::MAX
        } else {
            (1u64 << bits) - 1
        };
        loop {
            let value = if bits <= 32 {
                (self.next_u32() >> (32 - bits)) as u64
            } else {
                let low = self.next_u32() as u64;
                let high = (self.next_u32() >> (64 - bits)) as u64;
                (low | (high << 32)) & mask
            };
            if value < upper as u64 {
                return value as i64;
            }
        }
    }
}

pub fn random_new(seed: i64) -> Random {
    let seed = seed.unsigned_abs();
    let keys = if seed == 0 {
        vec![0]
    } else if seed <= u32::MAX as u64 {
        vec![seed as u32]
    } else {
        vec![seed as u32, (seed >> 32) as u32]
    };
    Random::new(&keys)
}

pub fn random_default() -> Result<Random> {
    let mut bytes = [0u8; 8];
    std::fs::File::open("/dev/urandom")?.read_exact(&mut bytes)?;
    Ok(random_new(i64::from_le_bytes(bytes) & i64::MAX))
}

pub fn random_random(random: &Random) -> f64 {
    let left = (random.next_u32() >> 5) as u64;
    let right = (random.next_u32() >> 6) as u64;
    ((left << 26) + right) as f64 / 9007199254740992.0
}

pub fn random_randrange(random: &Random, start: i64, stop: i64) -> Result<i64> {
    let width = stop
        .checked_sub(start)
        .ok_or("empty range for randrange()")?;
    if width <= 0 {
        return Err("empty range for randrange()".into());
    }
    Ok(start + random.below(width))
}
