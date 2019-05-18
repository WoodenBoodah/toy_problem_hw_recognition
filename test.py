from __future__ import print_function

import numpy as np
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.autograd import Variable


class Args:
    def __init__(self):
        self.cuda = True
        self.no_cuda = False
        self.seed = 1
        self.batch_size = 50
        self.test_batch_size = 1000
        self.epochs = 10
        self.lr = 0.01
        self.momentum = 0.5
        self.log_interval = 10


args = Args()

args.cuda = not args.no_cuda and torch.cuda.is_available()

torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)

kwargs = {'num_workers': 1, 'pin_memory': True} if args.cuda else {}

train_loader = torch.utils.data.DataLoader(
    datasets.MNIST(
        '../data',
        train=True,
        download=True,
        transform=transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307, ), (0.3081, ))
        ])),
    batch_size=args.batch_size,
    shuffle=True,
    **kwargs)

test_loader = torch.utils.data.DataLoader(
    datasets.MNIST(
        '../data',
        train=False,
        transform=transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307, ), (0.3081, ))
        ])),
    batch_size=args.test_batch_size,
    shuffle=True,
    **kwargs)

class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv1 = nn.Conv2d(1, 10, kernel_size=5)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(320, 50)
        self.fc2 = nn.Linear(50, 10)

    def forward(self, x):
        print('CNN in shape: ', x.shape)

        x = self.conv1(x)
        x = F.max_pool2d(x, 2)
        x = F.relu(x)
        # x = F.relu(F.max_pool2d(self.conv1(x), 2))

        x = self.conv2(x)
        x = F.max_pool2d(x, 2)
        x = F.relu(x)
        # x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))

        print('CNN out shape: ', x.shape)

        x = x.view(-1, 320)
        # print('CNN out shape (after x.view): ', x.shape)
        # x = F.relu(self.fc1(x))
        # x = F.dropout(x, training=self.training)
        # x = self.fc2(x)
        # return F.log_softmax(x, dim=1)
        return x


class Combine(nn.Module):
    def __init__(self):
        super(Combine, self).__init__()
        self.cnn = CNN()
        self.rnn = nn.LSTM(
            input_size=160,
            hidden_size=64,
            num_layers=1,
            batch_first=True)
        self.linear = nn.Linear(64, 10)

    def forward(self, x):
        print('RNN in shape: ', x.shape)
        # batch_size, timesteps, C, H, W = x.size()
        batch_size,  C, H, W = x.size()
        c_in = x.view(batch_size, C, H, W)
        timesteps = 2
        c_out = self.cnn(c_in)

        print(c_out.shape)
        r_in = c_out.view(batch_size, timesteps, -1)
        # print(r_in.shape)

        r_out, (h_n, h_c) = self.rnn(r_in)
        r_out2 = self.linear(r_out[:, -1, :])

        # print('RNN out shape: ', r_out.shape)

        return F.log_softmax(r_out2, dim=1)


model = Combine()
if args.cuda:
    model.cuda()

optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=args.momentum)


def train(epoch):
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):

        # print('Data shape: ', data.shape)

        # data = np.expand_dims(data, axis=1)
        data = torch.FloatTensor(data)
        if args.cuda:
            data, target = data.cuda(), target.cuda()

        # print('Data shape (after expand): ', data.shape, '; Target shape: ', target.shape)

        data, target = Variable(data), Variable(target)
        optimizer.zero_grad()
        output = model(data)

        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()
        if batch_idx % args.log_interval == 0:
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                       100. * batch_idx / len(train_loader), loss.item()))


def test():
    model.eval()
    test_loss = 0
    correct = 0
    for data, target in test_loader:

        data = np.expand_dims(data, axis=1)
        data = torch.FloatTensor(data)
        print(target.size)

        if args.cuda:
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data, volatile=True), Variable(target)
        output = model(data)
        test_loss += F.nll_loss(
            output, target, size_average=False).item()  # sum up batch loss
        pred = output.data.max(
            1, keepdim=True)[1]  # get the index of the max log-probability
        correct += pred.eq(target.data.view_as(pred)).long().cpu().sum()

    test_loss /= len(test_loader.dataset)
    print(
        '\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
            test_loss, correct, len(test_loader.dataset),
            100. * correct / len(test_loader.dataset)))


for epoch in range(1, args.epochs + 1):
    train(epoch)
    test()