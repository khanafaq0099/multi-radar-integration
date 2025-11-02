import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import LinearLocator

plt.ion()  # interactive mode

fig = plt.figure()
ax1 = fig.add_subplot(111, projection='3d')

ax1.set_xlim(0, 3)
ax1.set_ylim(0, 3)
ax1.set_zlim(0, 3)

ax1.xaxis.set_major_locator(LinearLocator(5))  # set axis scale
ax1.yaxis.set_major_locator(LinearLocator(3))
ax1.zaxis.set_major_locator(LinearLocator(3))
ax1.set_xlabel('x')
ax1.set_ylabel('y')
ax1.set_zlabel('z')
ax1.set_title('Radar')
# Some sample data
# x = np.linspace(-5, 5, 100)
# y = np.linspace(-5, 5, 100)
# X, Y = np.meshgrid(x, y)
# Z = np.sin(np.sqrt(X**2 + Y**2))

# Create the surface
# surf = ax1.plot_surface(X, Y, Z, cmap='viridis')

plt.show(block=True)  # optional in some IDEs
